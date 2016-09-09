# -*- coding: utf-8 -*-
import os
import time
import re
import logging
import datetime
import json
import requests
import hashlib

from random import Random
from collections import OrderedDict

#from django.conf import settings
#from django.core.exceptions import ImproperlyConfigured

#from llt.utils import random_str, smart_str
#from llt.url import sign_url
#from reconciliations.models import BillLog
#from core.models import ChannelAccount

# Get an instance of a logger
logger = logging.getLogger(__name__)

# 微信下载bill的时间,每日13点
GET_BILL_TIME = 13

def dict_to_xml(params, sign):
    xml = ['<xml>']
    for (k, v) in params.items():
        if v.isdigit():
            xml.append('<%s>%s</%s>' % (k, v, k))
        else:
            xml.append('<%s><![CDATA[%s]]></%s>' % (k, v, k))

    if sign:
        xml.append('<sign><![CDATA[%s]]></sign>' % sign)
    xml.append('</xml>')
    return ''.join(xml)


def xml_to_dict(xml):
    #print(xml)
    if xml[0:5].upper() != "<XML>" and xml[-6].upper() != "</XML>":
        return None, None

    result = {}
    sign = None
    content = ''.join(xml[5:-6].strip().split('\n'))

    pattern = re.compile(r'<(?P<key>.+)>(?P<value>.+)</(?P=key)>')
    m = pattern.match(content)
    while m:
        key = m.group('key').strip()
        value = m.group('value').strip()
        if value != '<![CDATA[]]>':
            pattern_inner = re.compile(r'<!\[CDATA\[(?P<inner_val>.+)\]\]>')
            inner_m = pattern_inner.match(value)
            if inner_m:
                value = inner_m.group('inner_val').strip()
            if key == 'sign':
                sign = value
            else:
                result[key] = value

        next_index = m.end('value') + len(key) + 3
        if next_index >= len(content):
            break
        content = content[next_index:]
        m = pattern.match(content)

    return sign, result


class WeChatConfig(object):
    def __init__(self, channel_config):
        self.app_id = channel_config['app_id']
        self.mch_id = channel_config['mch_id']
        self.api_key = channel_config['api_key']
        #self.app_secret = channel_config['app_secret']
        self.api_cert_file = channel_config['api_cert_file']
        self.api_key_file = channel_config['api_key_file']
        self.notify_url = channel_config['notify_url']
        self.jsapi_ticket_id = channel_config.get('jsapi_ticket_id', '')
        self.jsapi_ticket_url = channel_config.get('jsapi_ticket_url', '')

    def __str__(self):
        return "WechatConfig object: " + str(self.__dict__)


class WeChatPay(object):

    def __init__(self, wechat_config):
        self.app_id = wechat_config.app_id
        self.mch_id = wechat_config.mch_id
        self.api_key = wechat_config.api_key
        #self.app_secret = wechat_config.app_secret
        self.cert_file = wechat_config.api_cert_file
        self.key_file = wechat_config.api_key_file
        self.notify_url = wechat_config.notify_url
        self.jsapi_ticket_id = wechat_config.jsapi_ticket_id
        self.jsapi_ticket_url = wechat_config.jsapi_ticket_url

        self.common_params = {'appid': self.app_id,
                              'mch_id': self.mch_id}
        self.params = {}
        self.url = 'https://api.mch.weixin.qq.com/pay/unifiedorder'

    def set_params(self, **kwargs):
        self.params = {}
        for (k, v) in kwargs['params'].items():
            self.params[k] = v#smart_str(v)

        self.params['nonce_str'] = random_str(length=32)
        self.params.update(self.common_params)

    def post_xml(self):
        xml = self.dict2xml(self.params)
        response = requests.post(self.url, data=xml)
        logger.info('Make post request to %s' % response.url)
        logger.debug('Request XML: %s' % xml)
        logger.debug('Response encoding: %s' % response.encoding)
        logger.debug('Response XML: %s' % ''.join(response.text.splitlines()))

        return self.xml2dict(response.text.encode(response.encoding)) if response.encoding else response.text

    def post_xml_ssl(self):
        xml = self.dict2xml(self.params)
        #print(xml)
        logger.debug('Cert file: %s' % self.cert_file)
        logger.debug('Key file: %s' % self.key_file)
        requests.encoding = 'utf-8'
        response = requests.post(
            self.url, data=xml.encode('utf-8'), verify=True, cert=(self.cert_file, self.key_file))
        logger.info('Make SSL post request to %s' % response.url)
        logger.debug('Request XML: %s' % xml)
        logger.debug('Response encoding: %s' % response.encoding)
        logger.debug('Response XML: %s' % ''.join(response.text.splitlines()))

        response.encoding = 'utf-8'        
        #return self.xml2dict(response.text.encode(response.encoding)) if response.encoding else response.text
        return self.xml2dict(response.text)
    def dict2xml(self, params, with_sign=True):
        #sign = sign_url(
            #params, self.api_key, key_name='key', upper_case=True) if with_sign else None
        sign = get_sign(params, self.api_key) if with_sign else None
        return dict_to_xml(params,sign)

    def xml2dict(self, xml):
        sign, params = xml_to_dict(xml)

        if not sign or not params:
            print('Convert xml to dict failed, xml: [%s]' % xml)
            params['return_code'] = 'FAIL'
            return params

        if params['appid'] != self.app_id or params['mch_id'] != self.mch_id:
            raise ValueError('Invalid appid or mch_id, appid: [%s], mch_id: [%s]' % (params['appid'],
                                                                                     params['mch_id']))

        if params['return_code'] != 'SUCCESS':
            raise ValueError('WeChat proccess request failed, return code: [%s], return msg: [%s]' %
                             (params['return_code'], params.get('return_msg', '')))

        #calc_sign = sign_url(
        #    params, self.api_key, key_name='key', upper_case=True)
        calc_sign = get_sign(params,self.api_key)
        if calc_sign != sign:
            raise ValueError(
                'Invalid sign, calculate sign: [%s], sign: [%s]' % (calc_sign, sign))

        if params['result_code'] != 'SUCCESS':
            logger.error('WeChat process request failed, result_code: [%s], err_code: [%s], err_code_des: [%s]' %
                         (params['result_code'], params.get('err_code', ''), params.get('err_code_des', '')))
        return params

    def get_jsapi_ticket(self):
        """
        获取jsapi_ticket
        :return: jsapi_ticket
        """

        params = {'wechatid': self.jsapi_ticket_id}
        response = requests.post(self.jsapi_ticket_url, data=params)
        logger.info('Make request to %s' % response.url)

        resp_dict = json.loads(response.content)

        if resp_dict['code'] == 0:
            # print resp_dict
            # print resp_dict['data']['jsapi_ticket']
            return resp_dict['data']['jsapi_ticket']
        else:
            logger.info('code: %s, data: %s' %
                        (resp_dict['code'], resp_dict['data']))
            return ''

    def get_js_config_params(self, url, nonce_str, time_stamp):
        """
        获取js_config初始化参数
        """
        params = {'noncestr': nonce_str,
                  'jsapi_ticket': self.get_jsapi_ticket(),
                  'timestamp': '%d' % time_stamp,
                  'url': url}

        # params['signature'] = calculate_sign(params, sign_type='sha1',
        # upper_case=False)
        params['signature'] = sign_url(params, '', sign_type='sha1')
        return params


class UnifiedOrderPay(WeChatPay):

    def __init__(self, wechat_config):
        super(UnifiedOrderPay, self).__init__(wechat_config)
        self.url = 'https://api.mch.weixin.qq.com/pay/unifiedorder'
        self.trade_type = ''

    def _post(self, body, out_trade_no, total_fee, spbill_create_ip, notify_url, **kwargs):
        params = {'body': body,
                  'out_trade_no': out_trade_no,
                  'total_fee': total_fee,
                  'spbill_create_ip': spbill_create_ip,
                  'notify_url': notify_url,
                  'trade_type': self.trade_type}
        params.update(**kwargs)

        self.set_params(**params)
        return self.post_xml()


class NativeOrderPay(UnifiedOrderPay):

    """
    Native 统一支付类
    """

    def __init__(self, wechat_config):
        super(NativeOrderPay, self).__init__(wechat_config)
        self.trade_type = 'NATIVE'

    def post(self, body, out_trade_no, total_fee, spbill_create_ip, notify_url):
        return super(NativeOrderPay, self)._post(body, out_trade_no, total_fee, spbill_create_ip, notify_url)


class AppOrderPay(UnifiedOrderPay):

    """
    App 统一支付类
    """

    def __init__(self, wechat_config):
        super(AppOrderPay, self).__init__(
            wechat_config)
        self.trade_type = 'APP'

    def post(self, body, out_trade_no, total_fee, spbill_create_ip, notify_url):
        return super(AppOrderPay, self)._post(body, out_trade_no, total_fee, spbill_create_ip, notify_url)


class JsAPIOrderPay(UnifiedOrderPay):

    """
    H5页面的js调用类
    """

    def __init__(self, wechat_config):
        super(JsAPIOrderPay, self).__init__(wechat_config)
        self.trade_type = 'JSAPI'

    def post(self, body, out_trade_no, total_fee, spbill_create_ip, notify_url, open_id, url):
        # 直接调用基类的post方法查询prepay_id，如果成功，返回一个字典
        print("starting to post...")
        unified_order = super(JsAPIOrderPay, self)._post(body, out_trade_no, total_fee, spbill_create_ip,
                                                         notify_url, open_id=open_id)
        print("post done!")
        nonce_str = random_str(length=32)
        time_stamp = time.time()

        pay_params = {'appId': self.app_id,
                      'timeStamp': '%d' % time_stamp,
                      'nonceStr': nonce_str,
                      'package': 'prepay_id=%s' % unified_order.get('prepay_id'),
                      'signType': 'MD5'}
        print("starting to sign url")
        pay_params['paySign'] = sign_url(
            pay_params, self.api_key, key_name='key', upper_case=True)

        print("sgin done!")

        unified_order.update({'pay_params': pay_params,
                              'config_params': self.get_js_config_params(url, nonce_str, time_stamp)})

        return unified_order


class WeChatOrderQuery(WeChatPay):

    def __init__(self, wechat_config):
        super(WeChatOrderQuery, self).__init__(wechat_config)
        self.url = 'https://api.mch.weixin.qq.com/pay/orderquery'

    def post(self, out_trade_no):
        params = {'out_trade_no': out_trade_no}
        #params = {'transaction_id': out_trade_no}
        self.set_params(params=params)
        return self.post_xml_ssl()


class WeChatNotify(WeChatPay):

    def __init__(self, wechat_config):
        super(WeChatNotify, self).__init__(wechat_config)

    def notify_process(self, xml):
        notice = self.xml2dict(xml)
        return notice

class WeChatCloseOrder(WeChatPay):

    def __init__(self, wechat_config):
        super(WeChatCloseOrder, self).__init__(wechat_config)
        self.url = 'https://api.mch.weixin.qq.com/pay/closeorder'

    def post(self, out_trade_no):
        params = {'out_trade_no': out_trade_no}
        self.set_params(params=params)
        return self.post_xml_ssl()

class Refund(WeChatPay):

    def __init__(self, wechat_config):
        super(Refund, self).__init__(wechat_config)
        self.url = 'https://api.mch.weixin.qq.com/secapi/pay/refund'

    def post(self, out_trade_no, out_refund_no, total_fee, refund_fee):
        params = {'out_trade_no': out_trade_no,
                  'out_refund_no': out_refund_no,
                  'total_fee': total_fee,
                  'refund_fee': refund_fee,
                  'op_user_id': self.mch_id}
        self.set_params(**params)
        return self.post_xml_ssl()


class RefundQuery(WeChatPay):

    def __init__(self, wechat_config):
        super(RefundQuery, self).__init__(wechat_config)
        self.url = 'https://api.mch.weixin.qq.com/pay/refundquery'

    def post(self, out_refund_no):
        params = {'out_refund_no': out_refund_no}
        self.set_params(**params)
        return self.post_xml()


class DownloadBill(WeChatPay):

    def __init__(self, wechat_config):
        super(DownloadBill, self).__init__(wechat_config)
        self.url = 'https://api.mch.weixin.qq.com/pay/downloadbill'
        self.unique_id = 'wechat_%s_%s' % (wechat_config.app_id, wechat_config.mch_id)
        self.channel_account = ChannelAccount.objects.get(unique_id=self.unique_id)

    def post_xml(self):
        xml = self.dict2xml(self.params)
        response = requests.post(self.url, data=xml)
        logger.info('Make post request to %s' % response.url)
        logger.debug('Request XML: %s' % xml)
        logger.debug('Response encoding: %s' % response.encoding)
        logger.debug('Response XML: %s' % ''.join(response.text.splitlines()))

        return self.xml2dict_for_bill(response.text.encode(response.encoding)) if response.encoding else response.text

    def xml2dict_for_bill(self, xml):
        sign, params = xml_to_dict(xml)
        return params

    def get_yesterday_date_str(self):
        today = datetime.date.today()
        t = datetime.timedelta(days=1)
        # e.g. 20150705
        yesterday = str(today - t)
        return yesterday

    def is_record_writen(self):
        bill_log = BillLog.objects.filter(
            date=self.bill_date, channel_account=self.channel_account)
        return bill_log

    def date_validation(self, input_date):
        today = datetime.date.today()
        t = datetime.timedelta(days=1)
        yesterday = (today - t)
        now = datetime.datetime.now()
        if input_date < today:
            if input_date == yesterday:
                if now.hour >= GET_BILL_TIME:
                    return True
                else:
                    raise ValueError(
                        "Get bill time:[%s] o‘clock must later then %s o‘clock." % (
                            now.hour, GET_BILL_TIME))
            else:
                return True
        else:
            raise ValueError(
                "Bill_date given: [%s] should before today's date: [%s]." % (input_date, today))

    def is_responese_string(self, res):
        if type(res) is unicode:
            return True
        elif type(res) is dict:
            return False
        else:
            raise Exception(u'Invalid response type %s.' % type(res))

    def get_res(self, bill_date=None, bill_type='ALL'):
        params = {}
        if bill_date:
            input_bill_date = datetime.datetime.strptime(
                bill_date, '%Y-%m-%d').date()
            if self.date_validation(input_bill_date):
                self.bill_date = str(input_bill_date)
        else:
            self.bill_date = self.get_yesterday_date_str()
        # reformat date string from yyyy-mm-dd to yyyymmdd
        print('input_date>>>', self.bill_date)
        self.rf_bill_date = self.bill_date.replace('-', '')

        params['bill_date'] = self.rf_bill_date
        params['bill_type'] = bill_type

        self.set_params(**params)

        return self.post_xml()

    def create_bill_log(self, bill_status, file_path, remark):
        BillLog.objects.create(date=self.bill_date,
                               bill_status=bill_status,
                               file_path=file_path,
                               remark=remark,
                               channel_account=self.channel_account,
                               )

    def get_bill(self, bill_date=None, bill_type='ALL'):
        res = self.get_res(bill_date, bill_type)

        month_dir = '%s' % self.rf_bill_date[:6]
        bill_file_dir = os.path.join(WC_BILLS_PATH, month_dir)
        if not os.path.exists(bill_file_dir):
            os.makedirs(bill_file_dir)

        self.file_path = os.path.join(
            bill_file_dir, "%s_%s.csv" % (self.unique_id, self.rf_bill_date))
        self.rel_dir_name = os.path.relpath(self.file_path)

        # 成功取回外部账单
        if self.is_responese_string(res):
            res = res.replace('`', '')

            if not self.is_record_writen():
                with open(self.file_path, "wb") as f:
                    f.write(res.encode("UTF-8"))
                    f.close()
                self.create_bill_log('SUCCESS', self.rel_dir_name, '{}')
        else:
            # 对账单文件为空，不创建，只写入数据库信息
            if res['return_msg'] == 'No Bill Exist':
                remark = json.dumps(res)
                if not self.is_record_writen():
                    self.create_bill_log('EMPTY', file_path='N/A', remark=remark)
            else:
                remark = json.dumps(res)
                if not self.is_record_writen():
                    self.create_bill_log('FAIL', file_path='N/A', remark=remark)

def get_sign(params, key):
    msg = OrderedDict(sorted(params.items()))
    s = ''
    for (k,v) in msg.items():
        s += k
        s += '='
        s += str(v)
        s += '&'
    s += 'key='
    #s = s[:-1]
    s += str(key)

    #print('Input string to md5[%s]' % s)
    m = hashlib.md5()
    m.update(s.encode('utf-8'))
    ret = m.hexdigest().upper()

    #print(ret)
    return(ret)

def random_str(length):
    str = ''
    chars = 'AaBbCcDdEeFfGgHhIiJjKkLlMmNnOoPpQqRrSsTtUuVvWwXxYyZz0123456789'
    count = len(chars) - 1
    random = Random()
    for i in range(length):
        str+=chars[random.randint(0, count)]
    return str
