from django.http import JsonResponse
from .models import Scene


def scene_to_dict(scene):
    """Превращает сцену в словарь для JSON"""
    choices_data = []
    for choice in scene.choices.all().order_by('order'):
        choices_data.append({
            'id': choice.id,
            'text': choice.text,
            'next_scene_slug': choice.next_scene.slug if choice.next_scene else None,
            'set_flag': choice.set_flag,
        })
    
    return {
        'id': scene.id,
        'slug': scene.slug,
        'title': scene.title,
        'text': scene.text,
        'location': scene.location,
        'scene_type': scene.scene_type,
        'choices': choices_data,
    }


def start_scene(request):
    """Возвращает стартовую сцену"""
    scene = Scene.objects.filter(is_start=True).first()
    if not scene:
        return JsonResponse({'error': 'Стартовая сцена не найдена'}, status=404)
    
    return JsonResponse(scene_to_dict(scene), json_dumps_params={'ensure_ascii': False})


def get_scene(request, slug):
    """Возвращает сцену по её slug"""
    try:
        scene = Scene.objects.get(slug=slug)
    except Scene.DoesNotExist:
        return JsonResponse({'error': f'Сцена "{slug}" не найдена'}, status=404)
    
    return JsonResponse(scene_to_dict(scene), json_dumps_params={'ensure_ascii': False})