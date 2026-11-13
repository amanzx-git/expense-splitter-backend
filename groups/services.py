from django.apps import apps
from django.db.models import Q


def has_active_financial_references(group, user_id):
    # B4/B6 supply these models. No financial rows can exist before then.
    try:
        expense = apps.get_model('expenses', 'Expense')
    except LookupError:
        expense = None
    if expense and expense.objects.filter(group=group, settlement__isnull=True, deleted_at__isnull=True).filter(
        Q(paid_by_id=user_id) | Q(created_by_id=user_id) | Q(shares__user_id=user_id)
    ).exists():
        return True
    try:
        payment = apps.get_model('settlements', 'SettlementTransaction')
    except LookupError:
        payment = None
    return bool(payment and payment.objects.filter(settlement__group=group, settlement__status='pending').filter(
        Q(payer_id=user_id) | Q(receiver_id=user_id)
    ).exists())
