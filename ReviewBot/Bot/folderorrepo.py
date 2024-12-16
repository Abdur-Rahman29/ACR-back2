from django.http import JsonResponse
from rest_framework.decorators import api_view
from Bot.utils import process_folder_or_repo, load_documents_from_files, handle_reviews
import os

from .config import *
from groq import Groq

client = Groq(api_key=groq_api_key)

import traceback  # For capturing the complete error traceback


@api_view(['POST'])
def initial_process(request):
    try:
        org_standards = request.FILES.get('org_file')
        directory = request.data.get('folder_or_repo')

        if not org_standards or not directory:
            return JsonResponse({'error': 'Both organizational standards file and directory must be provided.'},
                                status=400)

        # Process the folder or repository
        code_files, folder_path_or_error = process_folder_or_repo(directory)
        if code_files is None:
            return JsonResponse({'error': folder_path_or_error}, status=400)
        print('code files: ',code_files)

        # Load organizational standards content
        org_standards_content = load_documents_from_files(org_standards)

        # Prepare to store all review data
        reviews_data = []

        # Process each code file and generate reviews
        for code_file in code_files:
            with open(code_file, 'r', encoding='utf-8') as file:
                file_content = file.read()

            # Generate review for the current file
            lang = os.path.splitext(code_file)[1][1:]
            full_review_data = handle_reviews(
                file_content, org_standards_content, client, 'llama3-8b-8192', lang,
                os.path.relpath(code_file, folder_path_or_error)
            )

            reviews_data.append({
                'file_path': os.path.relpath(code_file, folder_path_or_error),
                'full_review': full_review_data,
                'content':file_content

            })
            print('reviews data: ',reviews_data)

        # Store necessary data in session (if needed)
        request.session['code_files'] = code_files
        request.session['relative_file_paths'] = [os.path.relpath(f, folder_path_or_error) for f in code_files]
        request.session['org_standards_content'] = org_standards_content
        request.session['reviews_data'] = reviews_data  # Store reviews data in session if needed

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
