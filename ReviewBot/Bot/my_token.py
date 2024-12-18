from rest_framework import status
import requests
from django.http import JsonResponse

# You should have your functions defined elsewhere for processing the PR (as you mentioned)
from rest_framework.decorators import api_view
from rest_framework.response import Response



@api_view(['POST'])
def git_token_generation(request):
    GITHUB_CLIENT_ID = "Ov23liAoWBA8cFwLh4ds"
    GITHUB_CLIENT_SECRET = "97bba278b113c6d649b591b6b30483146b9b274f"
    token = request.session.get('gittoken')

    if not token:
        # If token not in session, proceed to fetch it
        code = request.data.get("code")

        if not code:
            return JsonResponse(
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
            token = response.json().get("access_token")
            # Store token in session for future use
            request.session['gittoken'] = token
        else:
            error = response.json().get("error", "Git Token exchange failed")
            return JsonResponse(
                {"error": error},
                status=status.HTTP_400_BAD_REQUEST,
            )

    # Use the token to get the user's email and username from GitHub API
    user_url = "https://api.github.com/user"
    user_emails_url = "https://api.github.com/user/emails"
    headers = {"Authorization": f"Bearer {token}"}

    # Fetch user data
    user_response = requests.get(user_url, headers=headers)
    if user_response.status_code != 200:
        return JsonResponse(
            {"error": "Failed to fetch user information"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    user_data = user_response.json()
    username = user_data.get("login")
    email = None

    # Fetch user email data
    emails_response = requests.get(user_emails_url, headers=headers)
    if emails_response.status_code == 200:
        emails_data = emails_response.json()
        print("Emails data:", emails_data)  # Debugging: log the email data

        # Find the primary verified email
        for email_entry in emails_data:
            if email_entry.get("primary") and email_entry.get("verified"):
                email = email_entry.get("email")
                break

        # Fallback to the first verified email
        if not email:
            for email_entry in emails_data:
                if email_entry.get("verified"):
                    email = email_entry.get("email")
                    break
    else:
        print("Failed to fetch emails:", emails_response.status_code, emails_response.text)

    print("Access Token:", token)
    print("Username:", username)
    print("Email:", email or "Email not available or unverified")

    return JsonResponse(
        {
            "access_token": token,
            "username": username,
            "email": email or "Email not available or unverified",
        },
        status=status.HTTP_200_OK,
    )


    
@api_view(['POST'])    
def ado_token_generation(request):
    ado_pat=request.session.get('adotoken')
    client_secret = "eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiIsIng1dCI6Im9PdmN6NU1fN3AtSGpJS2xGWHo5M3VfVjBabyJ9.eyJjaWQiOiIxNDllNjNjYS01ODcyLTQ5Y2QtOTE1YS1iYjU4MTEyNWVlZmIiLCJjc2kiOiIzMmY3M2Y1NC1jOGNhLTQyMzQtYjczYi0zYmQ5OGJlNzA2OTQiLCJuYW1laWQiOiJhZDhmNzZkMi01NWNiLTQ5YjQtYjdkZS0yNWUwZjJkMGEwM2IiLCJpc3MiOiJhcHAudnN0b2tlbi52aXN1YWxzdHVkaW8uY29tIiwiYXVkIjoiYXBwLnZzdG9rZW4udmlzdWFsc3R1ZGlvLmNvbSIsIm5iZiI6MTczMzcyNjU3NSwiZXhwIjoxODkxNDk0MTM2fQ.c6YqwTfpViAoksh11wRD5l5KdGkECEuGGKcM1psVcZ20zABjQ3mrsJAhOCrFEH1vjiSt_oaA9c-1p_KXQcAmmzHyJ_O8BKA2cLKn1rJARLvtnBZKn04dXKDgbc7aDFYARXGQ6uqL134_3utAvGzDNzvmc5WpGmP2GZIj-dEaWeI37yjnlV4tMuUU2ZolEkNe9HJZwXmVSBrA-PXjlLovyk8BQ6R0VeS_oWgHivfpPPdPswXOrpUie8sQSWooemFfBGDIh4MEiFitsFnL7c-oOlmCG4uhj_tRPZbCz_qb6irHUfkmc0lQ5OYhPwgSgq117d51arsXLbmDJWQJ074AoA"
    
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
        print(response)
        if response.status_code == 200:
            response_data = response.json()
            ado_pat = response_data.get('access_token')
            request.session['adotoken'] = ado_pat
        else:
            error = response.json().get("error", "ADO Token exchange failed")
            return JsonResponse(
                {"error": error},
                status=status.HTTP_400_BAD_REQUEST
            )
    user_url = "https://app.vssps.visualstudio.com/_apis/profile/profiles/me?api-version=7.1-preview.1"
    headers = {"Authorization": f"Bearer {ado_pat}"}

    user_response = requests.get(user_url, headers=headers)
    if user_response.status_code == 200:
        user_data = user_response.json()
        username = user_data.get("displayName")
        email = user_data.get("emailAddress")
        
        return JsonResponse(
            {
                "access_token": ado_pat,
                "username": username,
                "email": email or "Email not available",
            },
            status=status.HTTP_200_OK,
        )
    else:
        return JsonResponse(
            {"error": "Failed to fetch user information"},
            status=status.HTTP_400_BAD_REQUEST,
        )
