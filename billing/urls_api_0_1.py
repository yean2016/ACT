from django.conf.urls import url

from billing import views
#from billing import records

urlpatterns = [
    url(r'^check/$', views.check_api, name='check_api'),
    url(r'^checkout/$', views.checkout_api, name='checkout_api'),
    url(r'^pay/$', views.pay_api, name='pay_api'),
    #url(r'^payment/$', views.payment_api, name='payment_api'),
    url(r'^pay_offline/$', views.pay_offline_api, name='pay_offline_api'),
    url(r'^monthly_card/$', views.monthly_card_api, name='monthly_card_api'),
    url(r'^prepay/get_order/wxpay/$', views.prepay_get_order_wxpay_api, name='prepay_get_order_wxpay_api'),
    url(r'^prepay/order_query/wxpay/$', views.prepay_order_query_wxpay_api, name='prepay_order_query_wxpay_api'),
    url(r'^prepay/notify/wxpay/$', views.prepay_notify_wxpay_api, name='prepay_notify_wxpay_api'),
    url(r'^prepay/close_order/wxpay/$', views.prepay_close_order_wxpay_api, name='prepay_close_order_wxpay_api'),
    url(r'^prepay/get_order/alipay/$', views.prepay_get_order_alipay_api, name='prepay_get_order_alipay_api'),
    url(r'^prepay/notify/alipay/$', views.prepay_notify_alipay_api, name='prepay_notify_alipay_api'),
    url(r'^prepay/get_order/unionpay/$', views.prepay_get_order_unionpay_api, name='prepay_get_order_unionpay_api'),
    url(r'^prepay/notify/unionpay/$', views.prepay_notify_unionpay_api, name='prepay_notify_unionpay_api'),
    #url(r'^billing_records/$', records.billing_records_api, name='billing_records_api'),
    #url(r'^prepay_records/$', records.prepay_records_api, name='prepay_records_api'),
    url(r'^$', views.billing_api, name='billing_api'),
]

