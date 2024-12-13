from django.http import JsonResponse
from rest_framework.decorators import api_view
from Bot.utils import load_documents_from_files, handle_reviews,process_ado_repo,extract_ado_info_from_url
import os

from groq import Groq
from .config import *

client = Groq(api_key=groq_api_key)

import traceback  # For capturing the complete error traceback
import base64,requests
client_secret="eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiIsIng1dCI6Im9PdmN6NU1fN3AtSGpJS2xGWHo5M3VfVjBabyJ9.eyJjaWQiOiIzMjZhZjk2MC1jZjdlLTQ4MjctOGEzMS1hNTZiNzRmMmJkZjUiLCJjc2kiOiIyOTIwNzU0Yy1hZWQ0LTRhOWQtODliZC0yZWM3M2UyYmZiMTEiLCJuYW1laWQiOiIzNWIwMDkxMS0zNmYzLTRmMWEtYjRlNi1jMTkyYzgzODgxZGUiLCJpc3MiOiJhcHAudnN0b2tlbi52aXN1YWxzdHVkaW8uY29tIiwiYXVkIjoiYXBwLnZzdG9rZW4udmlzdWFsc3R1ZGlvLmNvbSIsIm5iZiI6MTczMzQ2NjkwOSwiZXhwIjoxODkxMjMzMzA5fQ.h-UoZwuTgMgyfXvL1nVrHTSsjJ6m9eiZVSn0ZgXVQLSI7wETVQAPfpgQhfROenraoIFz9z7b4XMslTQ-TR4MBTE4633xLEtcolgCIuuLaBHm_2XB4TAetew9bhrcn4Ud6FaiPmxDnkRM8Bnj0YBIrB-0aWIZktexlAax03xg-iGAX0zXuu_56rAwlHGvZ-Eb2IOfznlMmPWADiXhL4QAx0VqrMsCT1YFJwxDV8OEvRdwdztGzBIei8hGXS0Hrg2wCb4zAPXMHoMmDLfwMzkJ62JzpI6Z84eHqoOKYhpj3CQjhIdcTQtG5hsrDjwu0JqCp8mf-OzVQ3CN5qojvGTxEw"

@api_view(['POST'])
def ado_repo(request):
    try:
        org_standards = request.FILES.get('org_file')
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
        ado_url = request.data.get('url')
        print(ado_pat)

        if not org_standards:
            return JsonResponse({'error': 'Organizational standards file must be provided.'},
                                status=400)
        if not ado_url:
            return JsonResponse({'error': 'Repo link must be provided.'},
                                status=400)
        if not ado_pat:
            return JsonResponse({'error': 'PAT must be provided.'},
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
                print('file path: ',reviews_data.display_path)

        return JsonResponse({'reviews_data': reviews_data}, safe=False)

    except Exception as e:
        # Capture and send the full traceback
        full_error = traceback.format_exc()
        return JsonResponse({'error': str(e), 'traceback': full_error}, status=500)
