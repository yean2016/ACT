# -*- coding: utf-8 -*-
# Generated by Django 1.9.1 on 2016-02-28 06:01
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0003_auto_20160228_1154'),
    ]

    operations = [
        migrations.RenameField(
            model_name='prepayorderwechatpay',
            old_name='responsetrade_type',
            new_name='response_trade_type',
        ),
    ]