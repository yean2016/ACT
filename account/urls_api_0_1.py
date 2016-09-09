from django.conf.urls import url

from account import views

urlpatterns = [
    url(r'^login/$', views.login_api, name='login_api'),
    url(r'^web_login/$', views.web_login_api, name='web_login_api'),
    url(r'^logout/$', views.logout_api, name='logout_api'),
    url(r'^verify/$', views.verify_api, name='verify_api'),
    url(r'^register/$', views.register_api, name='register_api'),
    url(r'^reset_password/$', views.reset_password_api,
                              name='reset_password_api'),
    url(r'^update_password/$', views.update_password_api,
                              name='update_password_api'),
    url(r'^reset_payment_password/$', views.reset_payment_password_api,
                              name='reset_payment_password_api'),
    url(r'^update_payment_password/$', views.update_payment_password_api,
                              name='update_payment_password_api'),
    url(r'^operator/$', views.operator_api, name='operator_api'),
]

