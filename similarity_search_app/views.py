import json
import sqlite3
import os
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from django.core.paginator import Paginator
from .models import CustomUser
from .vector_utils import VectorSearchManager


def signup(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')
        first_name = request.POST.get('first_name', '')
        last_name = request.POST.get('last_name', '')

        if password != confirm_password:
            messages.error(request, 'Passwords do not match.')
            return render(request, 'signup.html')

        if CustomUser.objects.filter(email=email).exists():
            messages.error(request, 'Email already exists.')
            return render(request, 'signup.html')

        try:
            user = CustomUser.objects.create_user(
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name
            )
            messages.success(request, 'Account created successfully. Please sign in.')
            return redirect('similarity_search_app:signin')
        except Exception as e:
            messages.error(request, f'Error creating account: {str(e)}')

    return render(request, 'signup.html')


def signin(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')

        user = authenticate(request, username=email, password=password)
        if user is not None:
            login(request, user)
            return redirect('similarity_search_app:home')
        else:
            messages.error(request, 'Invalid email or password.')

    return render(request, 'signin.html')


def signout(request):
    logout(request)
    return redirect('similarity_search_app:signin')


@login_required
def home(request):
    return render(request, 'home.html')


@login_required
@csrf_exempt
def search_ajax(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            source_type = data.get('source_type')
            keyword = data.get('keyword')
            page = int(data.get('page', 1))

            if not source_type or not keyword:
                return JsonResponse({'error': 'Source type and keyword are required'}, status=400)

            # Initialize vector search manager
            search_manager = VectorSearchManager()

            # Perform similarity search
            results = search_manager.similarity_search(source_type, keyword, limit=25)

            # Paginate results
            paginator = Paginator(results, 5)  # 5 results per page
            page_obj = paginator.get_page(page)

            # Format results for JSON response
            formatted_results = []
            for result in page_obj:
                formatted_results.append({
                    'id': result['id'],
                    'source_text': result['source_text'][:100] + '...' if len(result['source_text']) > 100 else result[
                        'source_text'],
                    'distance': round(result['distance'], 4),
                    'metadata': result['metadata']
                })

            return JsonResponse({
                'results': formatted_results,
                'has_next': page_obj.has_next(),
                'has_previous': page_obj.has_previous(),
                'current_page': page_obj.number,
                'total_pages': paginator.num_pages,
                'total_results': paginator.count
            })

        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

    return JsonResponse({'error': 'Invalid request method'}, status=405)


@login_required
@csrf_exempt
def source_detail(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            source_type = data.get('source_type')
            source_id = data.get('source_id')

            if not source_type or not source_id:
                return JsonResponse({'error': 'Source type and ID are required'}, status=400)

            # Get source detail from database
            db_path = settings.VECTOR_DATABASES[source_type]
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            cursor.execute("SELECT * FROM source_tbl WHERE id = ?", (source_id,))
            result = cursor.fetchone()
            conn.close()

            if result:
                # Get column names
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                cursor.execute("PRAGMA table_info(source_tbl)")
                columns = [column[1] for column in cursor.fetchall()]
                conn.close()

                # Create dictionary with column names and values
                source_detail = dict(zip(columns, result))
                return JsonResponse({'source_detail': source_detail})
            else:
                return JsonResponse({'error': 'Source not found'}, status=404)

        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

    return JsonResponse({'error': 'Invalid request method'}, status=405)