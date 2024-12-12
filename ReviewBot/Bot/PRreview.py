from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
import os
import requests
from django.http import JsonResponse

# You should have your functions defined elsewhere for processing the PR (as you mentioned)
from .utils import process_pull_request, fetch_file_content, handle_file_status, display_error_tabs, handle_reviews, \
    load_documents_from_files
from github import GithubException

from .config import *
from groq import Groq

client = Groq(api_key=groq_api_key)

from github import Github
from urllib.parse import urlparse
from rest_framework.response import Response
GITHUB_CLIENT_ID = "Ov23liAoWBA8cFwLh4ds"
GITHUB_CLIENT_SECRET = "97bba278b113c6d649b591b6b30483146b9b274f"

@api_view(['POST'])
def handle_pr_operations(request):
    """

    Fetch all PRs and their associated files using the GitHub token and repository URL.

    """
    code = request.data.get("code")

    if not code:
        return Response(
            {"error": "Authorization code not provided"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # GitHub API Token Exchange
    token_url = "https://github.com/login/oauth/access_token"
    headers = {"Accept": "application/json"}
    data = {
        "client_id": GITHUB_CLIENT_ID,
        "client_secret": GITHUB_CLIENT_SECRET,
        "code": code,
    }

    response = requests.post(token_url, headers=headers, data=data)

    if response.status_code == 200:
        access_token = response.json().get("access_token")
    else:
        error = response.json().get("error", "Token exchange failed")
        return Response(
            {"error": error},
            status=status.HTTP_400_BAD_REQUEST,
        )
    org_standards = request.FILES.get('orgFile')
    org_standards=load_documents_from_files(org_standards)
    request.session['org_file']=org_standards
    token = access_token
    request.session['token']=token
    print(token)

    repo_url = request.data.get('repo_link')
    request.session['repo_url']=repo_url
    if not org_standards:
        return Response({"detail": "Org are required."}, status=status.HTTP_400_BAD_REQUEST)

    if not token or not repo_url:
        return Response({"detail": "Token and repository link are required."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        # Normalize the URL by removing ".git" and adding a trailing slash if missing
        repo_url = repo_url.rstrip('/').replace('.git', '')

        # Parse the URL
        parsed_url = urlparse(repo_url)

        # Extract path parts and ensure the URL contains at least owner and repo name
        path_parts = parsed_url.path.strip('/').split('/')
        if len(path_parts) < 2:
            return Response({"detail": "Invalid repository URL format."}, status=status.HTTP_400_BAD_REQUEST)

        # Extract owner and repository name
        owner = path_parts[-2]
        repo_name = path_parts[-1]

        # Initialize the GitHub client
        g = Github(token)

        # Get the repository object
        repo = g.get_repo(f"{owner}/{repo_name}")

        # Fetch all pull requests

        pull_requests = repo.get_pulls(state='open')

        prs_data = []

        for pr in pull_requests:

            # Fetch files associated with the PR
            if not pr.is_merged():
                files = [f.filename for f in pr.get_files()]

                prs_data.append({

                    "id": pr.id,

                    "number": pr.number,

                    "files": files,

                })

        return Response({"prs": prs_data}, status=status.HTTP_200_OK)

    except Exception as e:

        return Response({"detail": f"Unexpected error: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def file_category(request):
    """
    Process all pull requests in the repository, categorize files by their status,
    and perform reviews for all files in all PRs.
    """
    # Validate input
    model_type = 'llama3-8b-8192'
    org_file = request.session.get('org_file')

    if not org_file:
        return Response({"detail": "Organizational standards file is required."}, status=status.HTTP_400_BAD_REQUEST)

    org_standards_content = org_file

    token = request.session.get('token')
    repo_url = request.session.get('repo_url')

    if not token or not repo_url:
        return Response({"detail": "Token and repository link are required."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        # Normalize the URL by removing ".git" and adding a trailing slash if missing
        repo_url = repo_url.rstrip('/').replace('.git', '')

        # Parse the URL
        parsed_url = urlparse(repo_url)

        # Extract path parts and ensure the URL contains at least owner and repo name
        path_parts = parsed_url.path.strip('/').split('/')
        if len(path_parts) < 2:
            return Response({"detail": "Invalid repository URL format."}, status=status.HTTP_400_BAD_REQUEST)

        # Extract owner and repository name
        owner = path_parts[-2]
        repo_name = path_parts[-1]

        # Initialize the GitHub client
        g = Github(token)

        # Get the repository object
        repo = g.get_repo(f"{owner}/{repo_name}")

        # Fetch all pull requests
        pull_requests = repo.get_pulls(state='open')
        all_reviews = {}

        for pr in pull_requests:
            pr_reviews = {}
            files = pr.get_files()
            file=[]
            for i in files:
                file.append(i.filename)
            print(files)
            # Access the repository details
            baserepo = pr.base.repo
            baseref = pr.base.ref
            headref = pr.head.ref

            # Process each file
            # Directly process all files without segregation
            allowed_extensions = ('.py', '.js', '.java', '.html', '.css', '.cpp')  # Allowed file extensions
            print("hi")
            for file in files:
                selected_file = file.filename  # Get the filename (or file path if needed)

                # If the file doesn't end with one of the allowed extensions, skip it
                if not selected_file.endswith(allowed_extensions):
                    continue
                lang = os.path.splitext(selected_file)[1][1:]  # Extract language based on file extension

                if not lang:
                    lang = 'unknown'

                try:
                    # Fetch the old and new file contents
                    old_content_str = fetch_file_content(baserepo, selected_file, baseref)
                    new_content_str = fetch_file_content(baserepo, selected_file, headref)
                except Exception as e:
                    print(f"Error fetching content for file {selected_file}: {str(e)}")
                    continue

                file_status, diff_json, is_deleted = handle_file_status(old_content_str, new_content_str)
                display_path = f"Reviewing: {selected_file} (From: {baseref} to {headref})"

                if is_deleted:
                    pr_reviews[file.filename] = {
                        "file_status": file_status,
                        "display_path": display_path,
                        "deleted_file": old_content_str,  # Include the content of the deleted file
                    }
                else:
                    try:
                        full_review_data = handle_reviews(
                            new_content_str,
                            org_standards_content,
                            client,  # Placeholder for the client, if applicable
                            model_type,
                            lang,
                            display_path
                        )
                    except Exception as e:
                        print(f"Error performing review for file {selected_file}: {str(e)}")
                        continue

                    pr_reviews[file.filename] = {
                        "old":old_content_str,
                        "new":new_content_str,
                        "file_status": file_status,
                        "display_path": display_path,
                        "diff_json": diff_json,  # Include diff information
                        "full_review": full_review_data,
                    }

            all_reviews[pr.number] = {
                "title": pr.title,
                "reviews": pr_reviews
            }

        return Response(all_reviews, status=status.HTTP_200_OK)

    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        return Response({"detail": f"Unexpected error: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



@api_view(['POST'])
def approve_pr(request):
    """
    Approve (merge) a pull request using the GitHub token and PR number.
    """
    token = request.session.get('token')
    repo_url = request.session.get('repo_url')
    pr_number = request.data.get('pr_number')

    if not token or not pr_number or not repo_url:
        return Response({"detail": "Token, PR number, and repository URL are required."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        # Normalize the URL by removing ".git" and adding a trailing slash if missing
        repo_url = repo_url.rstrip('/').replace('.git', '')

        # Parse the URL
        parsed_url = urlparse(repo_url)

        # Extract path parts and ensure the URL contains at least owner and repo name
        path_parts = parsed_url.path.strip('/').split('/')
        if len(path_parts) < 2:
            return Response({"detail": "Invalid repository URL format."}, status=status.HTTP_400_BAD_REQUEST)

        # Extract owner and repository name
        owner = path_parts[-2]
        repo_name = path_parts[-1]

        # Initialize the GitHub client
        g = Github(token)

        # Get the repository object
        repo = g.get_repo(f"{owner}/{repo_name}")

        # Fetch the PR by its number
        pr = repo.get_pull(pr_number)

        # Merge the PR
        pr.merge()

        return Response({"detail": f"Pull request #{pr_number} has been approved and merged."}, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({"detail": f"Unexpected error: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)