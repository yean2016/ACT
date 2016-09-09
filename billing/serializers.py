from rest_framework import serializers
from billing.models import OfflinePayment

class OfflinePaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = OfflinePayment
        #fields = ('id','plate_number','parking_card_number','payment_time','parking_lot','amount',)
        fields = ('plate_number','payment_time','parking_lot','amount',)

