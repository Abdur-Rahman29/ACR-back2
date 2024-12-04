from django.http import JsonResponse
from rest_framework.decorators import api_view
from Bot.utils import load_documents_from_files, handle_reviews,process_ado_repo,extract_ado_info_from_url
import os

from groq import Groq
from .config import *

client = Groq(api_key=groq_api_key)

import traceback  # For capturing the complete error traceback
import base64,requests

@api_view(['POST'])
def ado_repo(request):
    try:
        org_standards = request.FILES.get('org_file')
        ado_pat = request.data.get('pat')
        ado_url = request.data.get('url')

        if not (org_standards and ado_pat and ado_url) :
            return JsonResponse({'error': 'Both organizational standards file and directory must be provided.'},
                                status=400)

        organization, project, repo_name = extract_ado_info_from_url(ado_url)

        if not organization or not project or not repo_name:
            return JsonResponse({'error': 'Invalid Azure DevOps URL.'}, status=400)

        try:
            # Process Azure DevOps repository and get file paths
            code_files = process_ado_repo(ado_pat, organization, project, repo_name)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

        if code_files is None:
            return JsonResponse({'error': 'no files present'}, status=400)

        # Load organizational standards content
        org_standards_content = load_documents_from_files(org_standards)

        # Prepare to store all review data
        reviews_data = []
        print(code_files)
        # Process each code file and generate reviews
        for code_file in code_files:
            auth_token = base64.b64encode(f":{ado_pat}".encode("utf-8")).decode("utf-8")
            headers = {
                "Authorization": f"Basic {auth_token}",
            }
            ado_base_url = f"https://dev.azure.com/{organization}/{project}/_apis/git/repositories/{repo_name}/items"
            params = {
                "path": code_file,  # Specify the file path to fetch its content
                "api-version": "6.0"
            }

            # Now make the API call using the properly defined headers
            response = requests.get(ado_base_url, headers=headers, params=params)

            if response.status_code == 200:
                file_content = response.text
                display_path=code_file.lstrip('/')

                lang = os.path.splitext(code_file)[1][1:]
                print(lang)

                # Generate review for the current file
                full_review_data = handle_reviews(
                    file_content, org_standards_content, client, 'llama3-8b-8192',lang,
                    display_path
                )

                reviews_data.append({
                    'file_path': display_path,
                    'full_review': full_review_data,
                    'content':file_content

                })

        return JsonResponse({'reviews_data': reviews_data}, safe=False)

    except Exception as e:
        # Capture and send the full traceback
        full_error = traceback.format_exc()
        return JsonResponse({'error': str(e), 'traceback': full_error}, status=500)


@api_view(['GET'])
def get_file_review(request):
    # Retrieve reviews data from the session
    reviews_data = request.session.get('reviews_data', [])

    if not reviews_data:
        return JsonResponse({'error': 'No review data found'}, status=404)

    return JsonResponse(reviews_data, safe=False)