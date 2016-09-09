from django.conf.urls import url

from operation import views

urlpatterns = [
    url(r'^vehicle_in/$', views.vehicle_in_api, name='vehicle_in_api'),
    url(r'^vehicle_out/$', views.vehicle_out_api, name='vehicle_out_api'),
    url(r'^offline_payment/$', views.offline_payment_api, name='offline_payment_api'),
    url(r'^online_payment/$', views.online_payment_api, name='online_payment_api'),
    url(r'^prepayment/$', views.prepayment_api, name='prepayment_api'),
    url(r'^parkinglot_online/$', views.parkinglot_online_api, name='parkinglot_online_api'),
    url(r'^parkinglot_connected/$', views.parkinglot_connected_api, name='parkinglot_connected_api'),
    url(r'^parkinglot_disconnected/$', views.parkinglot_disconnected_api, name='parkinglot_disconnected_api'),
    url(r'^mobile_app/version/$', views.file_upload_api, name='file_upload_api'),
]

