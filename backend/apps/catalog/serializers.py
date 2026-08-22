from rest_framework import serializers


class CatalogItemSerializer(serializers.Serializer):
    provider = serializers.CharField()
    external_id = serializers.CharField()
    title = serializers.CharField()
    category = serializers.CharField()
    image_url = serializers.CharField(allow_blank=True)
    description = serializers.CharField(allow_blank=True)
    subtitle = serializers.CharField(allow_blank=True)
    suggested_venue_name = serializers.CharField(allow_blank=True)
    suggested_address = serializers.CharField(allow_blank=True)
    suggested_city = serializers.CharField(allow_blank=True)
    suggested_date_time = serializers.DateTimeField(allow_null=True)
    suggested_age_rating = serializers.CharField(allow_blank=True)
