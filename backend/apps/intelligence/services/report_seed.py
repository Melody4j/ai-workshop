from apps.intelligence.models import IntelligenceFeed


def has_seed_reports() -> bool:
    return IntelligenceFeed.objects.exists()
