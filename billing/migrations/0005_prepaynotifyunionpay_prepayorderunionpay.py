# -*- coding: utf-8 -*-
# Generated by Django 1.9.1 on 2016-03-08 07:43
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0004_auto_20160228_1401'),
    ]

    operations = [
        migrations.CreateModel(
            name='PrePayNotifyUnionPay',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('version', models.CharField(max_length=10)),
                ('encoding', models.CharField(max_length=10)),
                ('cert_id', models.CharField(max_length=32)),
                ('sign_method', models.CharField(max_length=10)),
                ('trade_type', models.CharField(max_length=10)),
                ('trade_subtype', models.CharField(max_length=10)),
                ('biz_type', models.CharField(max_length=10)),
                ('access_type', models.CharField(max_length=10)),
                ('merchant_id', models.CharField(max_length=32)),
                ('order_id', models.CharField(max_length=32)),
                ('trade_time', models.CharField(max_length=30)),
                ('trade_amount', models.CharField(max_length=13)),
                ('currency_code', models.CharField(max_length=10)),
                ('query_id', models.CharField(max_length=32)),
                ('resp_code', models.CharField(max_length=10)),
                ('resp_msg', models.CharField(max_length=50)),
                ('settle_amount', models.CharField(max_length=13)),
                ('settle_currency_code', models.CharField(max_length=10)),
                ('settle_date', models.CharField(max_length=30)),
                ('trace_no', models.CharField(max_length=32)),
                ('trace_time', models.CharField(max_length=30)),
                ('prepay_order', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='billing.PrePayOrder')),
            ],
        ),
        migrations.CreateModel(
            name='PrePayOrderUnionPay',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('version', models.CharField(max_length=10)),
                ('encoding', models.CharField(max_length=10)),
                ('sign_method', models.CharField(max_length=10)),
                ('trade_type', models.CharField(max_length=10)),
                ('trade_subtype', models.CharField(max_length=10)),
                ('biz_type', models.CharField(max_length=10)),
                ('channel_type', models.CharField(max_length=10)),
                ('back_url', models.CharField(max_length=80)),
                ('access_type', models.CharField(max_length=10)),
                ('merchant_id', models.CharField(max_length=32)),
                ('order_id', models.CharField(max_length=32)),
                ('trade_time', models.CharField(max_length=30)),
                ('trade_amount', models.CharField(max_length=13)),
                ('currency_code', models.CharField(max_length=10)),
                ('pay_timeout', models.CharField(max_length=30)),
                ('order_description', models.CharField(max_length=50)),
                ('response_version', models.CharField(max_length=10)),
                ('response_encoding', models.CharField(max_length=10)),
                ('response_sign_method', models.CharField(max_length=10)),
                ('response_trade_type', models.CharField(max_length=10)),
                ('response_trade_subtype', models.CharField(max_length=10)),
                ('response_biz_type', models.CharField(max_length=10)),
                ('response_access_type', models.CharField(max_length=10)),
                ('response_merchant_id', models.CharField(max_length=32)),
                ('response_order_id', models.CharField(max_length=32)),
                ('response_trade_time', models.CharField(max_length=30)),
                ('cert_id', models.CharField(max_length=32)),
                ('tn', models.CharField(max_length=32)),
                ('resp_code', models.CharField(max_length=10)),
                ('resp_msg', models.CharField(max_length=50)),
                ('prepay_order', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='billing.PrePayOrder')),
            ],
        ),
    ]
