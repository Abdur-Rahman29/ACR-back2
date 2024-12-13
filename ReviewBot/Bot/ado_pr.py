from requests.auth import HTTPBasicAuth
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from .utils import load_documents_from_files, handle_reviews, extract_ado_info_from_url, handle_file_status,update_pr_vote,get_authenticated_user_email,get_reviewer_id
import os
import requests
from .config import *
from groq import Groq
from .utils import get_reviewer_id,get_authenticated_user_email, complete_pull_request,add_pr_comment
client = Groq(api_key=groq_api_key)
import base64
client_secret="eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiIsIng1dCI6Im9PdmN6NU1fN3AtSGpJS2xGWHo5M3VfVjBabyJ9.eyJjaWQiOiIzMjZhZjk2MC1jZjdlLTQ4MjctOGEzMS1hNTZiNzRmMmJkZjUiLCJjc2kiOiIyOTIwNzU0Yy1hZWQ0LTRhOWQtODliZC0yZWM3M2UyYmZiMTEiLCJuYW1laWQiOiIzNWIwMDkxMS0zNmYzLTRmMWEtYjRlNi1jMTkyYzgzODgxZGUiLCJpc3MiOiJhcHAudnN0b2tlbi52aXN1YWxzdHVkaW8uY29tIiwiYXVkIjoiYXBwLnZzdG9rZW4udmlzdWFsc3R1ZGlvLmNvbSIsIm5iZiI6MTczMzQ2NjkwOSwiZXhwIjoxODkxMjMzMzA5fQ.h-UoZwuTgMgyfXvL1nVrHTSsjJ6m9eiZVSn0ZgXVQLSI7wETVQAPfpgQhfROenraoIFz9z7b4XMslTQ-TR4MBTE4633xLEtcolgCIuuLaBHm_2XB4TAetew9bhrcn4Ud6FaiPmxDnkRM8Bnj0YBIrB-0aWIZktexlAax03xg-iGAX0zXuu_56rAwlHGvZ-Eb2IOfznlMmPWADiXhL4QAx0VqrMsCT1YFJwxDV8OEvRdwdztGzBIei8hGXS0Hrg2wCb4zAPXMHoMmDLfwMzkJ62JzpI6Z84eHqoOKYhpj3CQjhIdcTQtG5hsrDjwu0JqCp8mf-OzVQ3CN5qojvGTxEw"
scope="vso.advsec_manage vso.analytics vso.auditstreams_manage vso.build_execute vso.code_full vso.code_status vso.connected_server vso.dashboards_manage vso.entitlements vso.environment_manage vso.extension.data_write vso.extension_manage vso.gallery_acquire vso.gallery_manage vso.githubconnections_manage vso.graph_manage vso.identity_manage vso.machinegroup_manage vso.memberentitlementmanagement_write vso.notification_diagnostics vso.notification_manage vso.packaging_manage vso.pipelineresources_manage vso.profile_write vso.project_manage vso.release_manage vso.securefiles_manage vso.security_manage vso.serviceendpoint_manage vso.symbols_manage vso.taskgroups_manage vso.test_write vso.threads_full vso.tokenadministration vso.tokens vso.variablegroups_manage vso.wiki_write vso.work_full"
state = "random_string_for_csrf_protection"
# Azure DevOps API details
ado_url_template = "https://dev.azure.com/{organization}/{project}/_apis/git"

def get_auth_header(pat):
    """Return authorization header with Basic authentication."""
    encoded_token = base64.b64encode(f":{pat}".encode()).decode()
    return {"Authorization": f"Basic {encoded_token}"}

def fetch_file_content_by_object_id(repo, object_id, ado_url, ado_pat):
    """Fetch file content by object ID."""
    url = f"{ado_url}/repositories/{repo}/blobs/{object_id}?api-version=7.0&$format=text"
    headers = get_auth_header(ado_pat)

    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.text
    else:
        print(f"Failed to fetch file content for Object ID {object_id}: {response.status_code} {response.text}")
        return None

def get_pull_requests(ado_url, repository, ado_pat):
    """Fetch pull requests from Azure DevOps."""
    url = f"{ado_url}/repositories/{repository}/pullrequests?api-version=7.0"
    headers = get_auth_header(ado_pat)

    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json().get('value', [])
    else:
        print(f"Failed to fetch PRs: {response.status_code} {response.text}")
        return []

def get_latest_iteration_id(pull_request_id, ado_url, ado_pat, repository):
    """Fetch the latest iteration ID for a PR."""
    url = f"{ado_url}/repositories/{repository}/pullRequests/{pull_request_id}/iterations?api-version=7.0"
    headers = get_auth_header(ado_pat)

    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        iterations = response.json().get('value', [])
        if iterations:
            return iterations[-1]['id']
    else:
        print(f"Failed to fetch iterations for PR {pull_request_id}: {response.status_code} {response.text}")
    return None

def get_pr_files(pull_request_id, ado_url, ado_pat, repository):
    """Fetch the files changed in a PR based on its latest iteration."""
    iteration_id = get_latest_iteration_id(pull_request_id, ado_url, ado_pat, repository)
    if iteration_id is None:
        return []

    url = f"{ado_url}/repositories/{repository}/pullRequests/{pull_request_id}/iterations/{iteration_id}/changes?api-version=7.0"
    headers = get_auth_header(ado_pat)

    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        print(response.json())
        return response.json().get('changeEntries', [])
    else:
        print(f"Failed to fetch files for PR {pull_request_id}: {response.status_code} {response.text}")
        return []
def get_pr_repository_info(pr):
    """Extract repository and ref info from PR data."""
    try:
        baserepo = pr['repository']['name']
        baseref = pr['targetRefName']
        headref = pr['sourceRefName']
        return baserepo, baseref, headref
    except KeyError as e:
        print(f"KeyError: Missing expected key {e} in PR data")
        return None, None, None

@api_view(['POST'])
def get_pr_data(request):
    ado_pat=request.session.get('token')
    if not ado_pat:
        authorization_code = request.data.get('code')
        token_url = "https://app.vssps.visualstudio.com/oauth2/token"
        redirect_uri="https://acr-front-code-review.apps.opendev.hq.globalcashaccess.us/"
        data = {
            'client_assertion_type': 'urn:ietf:params:oauth:client-assertion-type:jwt-bearer',
            'client_assertion': client_secret,
            'grant_type': 'urn:ietf:params:oauth:grant-type:jwt-bearer',
            'assertion': authorization_code,
            'redirect_uri': redirect_uri
        }

        response = requests.post(token_url, data=data)
        response_data = response.json()

        # Step 3: Use the access token
        ado_pat = response_data.get('access_token')
        request.session['token']=ado_pat
    ado_url = request.data.get('repo_link')
    org_standards = request.FILES.get('orgFile')
    org_standards_content = load_documents_from_files(org_standards)
    if not org_standards:
        return Response({'error': 'Organizational standards file must be provided.'},
                            status=400)
    if not ado_url:
        return Response({'error': 'Repo link must be provided.'},
                            status=400)
    if not ado_pat:
        return Response({'error': 'PAT must be provided.'},
                            status=400)

    global organization, project, repository
    organization, project, repository = extract_ado_info_from_url(ado_url)
    ado_url = ado_url_template.format(organization=organization, project=project)

    try:
        pull_requests = get_pull_requests(ado_url, repository, ado_pat)
        all_reviews = {}

        for pr in pull_requests:
            pr_reviews = {}
            pr_number = pr['pullRequestId']
            pr_title = pr.get('title', 'No Title')
            print(f"Processing PR: {pr_number}")

            files = get_pr_files(pr_number, ado_url, ado_pat, repository)
            filenames = []
            baserepo, baseref, headref = get_pr_repository_info(pr)
            headref = headref.replace("refs/heads/", "")
            baseref = baseref.replace("refs/heads/", "")
            for file_entry in files:
                
                object_id_head = file_entry['item'].get('objectId')
                object_id_base = file_entry['item'].get('originalObjectId')

                if not object_id_head and not object_id_base:
                    print(f"Missing object IDs for {file_path}, skipping.")
                    continue
                if object_id_head:
                    file_path = file_entry['item']['path']
                else:
                    file_path=file_entry['originalPath']
                if not file_path.endswith(('.py', '.js', '.java', '.html', '.css', '.cpp')):
                    continue
                file_path = file_path.lstrip('/')
                filenames.append(file_path)
                old_content=None
                new_content=None
                if object_id_base:
                    old_content = fetch_file_content_by_object_id(repository, object_id_base, ado_url, ado_pat)
                
                if object_id_head:
                    new_content = fetch_file_content_by_object_id(repository, object_id_head, ado_url, ado_pat)

                file_status, diff_json, is_deleted = handle_file_status(old_content, new_content)
                display_path = f"Reviewing: {file_path} (From: {baseref} to {headref})"

                if is_deleted:
                    try:
                        full_review_data = handle_reviews(
                            old_content,
                            org_standards_content,
                            client,
                            "llama3-8b-8192",
                            os.path.splitext(file_path)[1][1:],
                            display_path,
                        )
                    except Exception as e:
                        print(f"Error reviewing {file_path}: {str(e)}")
                        continue
                else:
                    try:
                        full_review_data = handle_reviews(
                            new_content,
                            org_standards_content,
                            client,
                            "llama3-8b-8192",
                            os.path.splitext(file_path)[1][1:],
                            display_path,
                        )
                    except Exception as e:
                        print(f"Error reviewing {file_path}: {str(e)}")
                        continue

                pr_reviews[file_path] = {
                    "old": old_content,
                    "new": new_content,
                    "file_status": file_status,
                    "display_path": display_path,
                    "diff_json": diff_json,
                    "full_review": full_review_data,
                }

            all_reviews[pr_number] = {
                "number": pr_number,
                "title": pr_title,
                "files": filenames,
                "reviews": pr_reviews,
            }

        return Response(all_reviews, status=status.HTTP_200_OK)

    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        return Response({"detail": f"Unexpected error: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



@api_view(['POST'])
def approve_pr(request):
    pr_number = request.data.get('pr_number')
    ado_pat = request.session.get('token')
    ado_url = request.data.get('repo_link')

    if not pr_number or not ado_pat or not ado_url:
        return Response({"detail": "PR number, token, and repository link are required."}, status=status.HTTP_400_BAD_REQUEST)

    # Add your logic to approve the PR here
    organization, project, repository = extract_ado_info_from_url(ado_url)
    try:
        unique_name = get_authenticated_user_email(ado_pat)
        reviewer_id=get_reviewer_id(ado_pat, organization, project, repository, pr_number,unique_name)
        update_pr_vote(ado_pat, organization, project, repository, pr_number, reviewer_id, 'approve')
        return Response({"detail": f"PR #{pr_number} approved successfully."}, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
def reject_pr(request):
    pr_number = request.data.get('pr_number')
    ado_pat = request.session.get('token')
    ado_url = request.data.get('repo_link')
    reason = request.data.get('reason')

    if not pr_number or not ado_pat or not ado_url or not reason:
        return Response({"detail": "PR number, token, repository link, and reason are required."}, status=status.HTTP_400_BAD_REQUEST)
    organization, project, repository = extract_ado_info_from_url(ado_url)
    # Add your logic to reject the PR here
    try:
        unique_name = get_authenticated_user_email(ado_pat)
        reviewer_id=get_reviewer_id(ado_pat, organization, project, repository, pr_number,unique_name)
        update_pr_vote(ado_pat, organization, project, repository, pr_number, reviewer_id, 'reject')
        add_pr_comment(ado_pat, organization, project, repository, pr_number, reason)
        return Response({"detail": f"PR #{pr_number} rejected successfully."}, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
def complete_pr(request):
    pr_number = request.data.get('pr_number')
    ado_pat = request.session.get('token')
    ado_url = request.data.get('repo_link')

    if not pr_number or not ado_pat or not ado_url:
        return Response({"detail": "PR number, token, and repository link are required."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        # Ensure pr_number is an integer
        pr_number = int(pr_number)
    except ValueError:
        return Response({"detail": "PR number must be an integer."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        complete_pull_request(pr_number, ado_url, ado_pat)
        return Response({"detail": f"PR #{pr_number} completed successfully."}, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
