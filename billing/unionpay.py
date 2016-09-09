# -*- coding: utf-8 -*-
import os
import time
import re
import logging
import datetime
import json
import requests
import hashlib
import rsa
import base64
import os.path
import pytz

try:
    from urlparse import parse_qs
except ImportError:
    from urllib.parse import parse_qs
try:
    from urllib import urlencode
except ImportError:
    from urllib.parse import urlencode
from hashlib import sha1
from OpenSSL import crypto
from OpenSSL.crypto import FILETYPE_PEM
#from datetime import datetime
from zipfile import ZipFile
#from .util.helper import LineObject

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

tz = pytz.timezone('Asia/Shanghai')

class TradeType(object):
    pay = '01'
    query = '00'
    revoke = '31'
    refund = '04'
    auth = '02'
    auth_revoke = '32'
    auth_complete = '03'
    auth_complete_revoke = '33'
    file_transfer = '76'
    # 00：查询交易
    # 01：消费
    # 02：预授权
    # 03：预授权完成
    # 04：退货
    # 05：圈存
    # 11：代收
    # 12：代付
    # 13：账单支付
    # 14：转账（保留）
    # 21：批量交易
    # 22：批量查询
    # 31：消费撤销
    # 32：预授权撤销
    # 33：预授权完成撤销
    # 71：余额查询
    # 72：实名认证-建立绑定关系
    # 73：账单查询
    # 74：解除绑定关系
    # 75：查询绑定关系
    # 77：发送短信验证码交易
    # 78：开通查询交易
    # 79：开通交易
    # 94：IC卡脚本通知


BizType = {
    '000101': '基金业务之股票基金',
    '000102': '基金业务之货币基金',
    '000201': 'B2C网关支付',
    '000301': '认证支付2.0',
    '000302': '评级支付',
    '000401': '代付',
    '000501': '代收',
    '000601': '账单支付',
    '000801': '跨行收单',
    '000901': '绑定支付',
    '000902': 'Token支付',
    '001001': '订购',
    '000202': 'B2B',
}


class ChannelType(object):

    Desktop = '07'
    Mobile = '08'


class AccType(object):
    card = '01'
    passbook = '02'
    iccard = '03'


class payCardType(object):

    unknown = '00'
    debit_card = '01'
    credit_card = '02'
    quasi_credit_acct = '03'
    all_in_one_card = '04'
    prepaid_acct = '05'
    semi_prepaid_acct = '06'


class UnionPayConfig(object):
    def __init__(self, channel_config):
        self.version = channel_config['version']
        self.encoding = channel_config['encoding']
        self.sign_method = channel_config['sign_method']
        self.trade_type = channel_config['trade_type']
        self.trade_subtype = channel_config['trade_subtype']
        self.biz_type = channel_config['biz_type']
        self.channel_type = channel_config['channel_type']
        self.back_url = channel_config['back_url']
        self.access_type = channel_config['access_type']
        self.merchant_id = channel_config['merchant_id']
        self.currency_code = channel_config['currency_code']
        self.order_description = channel_config['order_description']
        self.pfx_file = channel_config['pfx_file']
        self.password = channel_config['pfx_password']
        self.x509_file = channel_config['x509_file']
        self.digest_method = 'sha1'
        self.app_trans_url = 'https://gateway.95516.com/gateway/api/appTransReq.do'

    def __str__(self):
        return "UnionPayConfig object: " + str(self.__dict__)


class UnionPay(object):

    def __init__(self, unionpay_config):
        self.signer = UnionPaySigner.getSigner(unionpay_config)#.sign_cert_file,
                          #unionpay_config.sign_cert_password,
                          #unionpay_config.verify_cert_file)
        self.timeout = 10
        self.verify = True
        self.params = {}

    def set_params(self, **kwargs):
        self.params = {}
        for (k, v) in kwargs['params'].items():
            self.params[k] = v#smart_str(v)

        #self.params.update(self.common_params)

    def get_txn_time(self):
        return datetime.datetime.now(tz).strftime('%Y%m%d%H%M%S')

    def get_timeout(self, trade_time=None, expire_minutes=10):
        '''
        @trade_time:        trade time
        @expire_minutes:    order expire minutes
        '''
        cur_trade_time = trade_time or datetime.datetime.now(tz)
        cur_trade_time += datetime.timedelta(minutes=expire_minutes)
        return cur_trade_time.strftime('%Y%m%d%H%M%S')

    def post(self, addr, data, **kwargs):
        try:
            response = requests.post(
                addr,
                data=data,
                timeout=self.timeout,
                verify=self.verify,
                cert=('unionpay_pfx.pem'),
            )
        except requests.ConnectionError:
            print('Connection to [' + addr +'] timeout.')
            content = 'respCode=408&respMsg=connection timeout'
            content += '&orderId=' + data['orderId']
            return content.encode('utf-8')

        if response.status_code != requests.codes.ok:
            msg = "[UPACP]request error: %s, reason: %s" \
                % (response.status_code, response.reason)
            #raise error.UnionpayError(msg)
        return response.content


    def send_packet(self, addr, data, **kwargs):
        raw_content = self.post(addr, data)
        data = self.signer.parse_arguments(raw_content.decode('utf-8'))

        #data = {'orderId': '20160304465468', 'signMethod': '01', 'txnTime': '20160304122638', 'merId': '898110257340256', 'respCode': '00', 'tn': '201603041226388584388', 'signature': 'iABKcOdvX5S3qsBwx  vCts47JvYJ5nFldZ97n9FnPxoqdXgbg381 MFP28oVkxKeEQbJTxS wqUUEIU N80kyelLKB4RMdKMVyjxL2WHhxl8zZf7U3mMuj6zS6fyqXMIPv15KTv xHlJNfv iJ76h2Xf64XS979FL5S3IWRsFRF3BNc7WamcFunsuIu2EUIFSWJmpmQuHicYFd1JGCHQYJ7O2Oy kz/LNqiaHmbWc3c0/SNW4smlQDtQsmy5iXyeygQ7bJkp/7mlFJqY62obwU6bAu4DSgvUAORtWJqp3v4vUuMlFmOBtnsruUqWw4iWXIyt/dzoXAW5MZL4scC0w==', 'bizType': '001001', 'version': '5.0.0', 'encoding': 'UTF-8', 'txnType': '01', 'certId': '69597475696', 'txnSubType': '01', 'respMsg': '成功[0000000]', 'accessType': '0'}
        #print(data)

        if data.get('respCode') != '00':
            logger.error(raw_content)
            msg = '[UPACP]respCode: %s orderid: %s' % (
                data['respCode'], data.get('orderId'))
            print(msg)
            return data

        try:
            self.signer.validate(data)
        except crypto.Error as errors:
            print('UnionPay response alidation failed: ' + str(errors))
            response = {}
            response['respCode'] = '422'
            response['respMsg'] = str(errors)
            return response

        return data


class UnifiedOrderPay(UnionPay):

    def __init__(self, unionpay_config):
        super(UnifiedOrderPay, self).__init__(unionpay_config)
        '''
        @pfx_filepath:      pfx file path
        @password:          pfx pem password
        @x509_filepath:     x509 file path
        @digest_method:     default digest method is sha1
        '''
        #self.digest_method = digest_method
        self.PKCS12 = self.loadPKCS12(self.sign_cert_file, self.sign_cert_password)
        #self.X509 = self.loadX509(x509_filepath)

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

    def sign(self, data):
        '''
        @data: a dict ready for sign, should not contain "signature" key name
        Return base64 encoded signature and set signature to data argument
        '''
        cert_id = self.PKCS12.get_certificate().get_serial_number()
        data['certId'] = str(cert_id)
        string_data = self.simple_urlencode(data)
        sign_digest = sha1(string_data).hexdigest()
        private_key = self.PKCS12.get_privatekey()
        soft_sign = self.sign_by_soft(
            private_key, sign_digest, self.digest_method)
        base64sign = base64.b64encode(soft_sign)
        data['signature'] = base64sign
        return base64sign


class NativeOrderPay(UnifiedOrderPay):

    """
    Native 统一支付类
    """

    def __init__(self, unionpay_config):
        super(NativeOrderPay, self).__init__(wechat_config)
        self.trade_type = 'NATIVE'

    def post(self, body, out_trade_no, total_fee, spbill_create_ip, notify_url):
        return super(NativeOrderPay, self)._post(body, out_trade_no, total_fee, spbill_create_ip, notify_url)


class AppOrderPay(UnifiedOrderPay):

    """
    App 统一支付类
    """

    def __init__(self, unionpay_config):
        super(AppOrderPay, self).__init__(
            wechat_config)
        self.trade_type = 'APP'

    def post(self, body, out_trade_no, total_fee, spbill_create_ip, notify_url):
        return super(AppOrderPay, self)._post(body, out_trade_no, total_fee, spbill_create_ip, notify_url)


class UnionPayOrderQuery(UnionPay):

    def __init__(self, wechat_config):
        super(WeChatOrderQuery, self).__init__(wechat_config)
        self.url = 'https://api.mch.weixin.qq.com/pay/orderquery'

    def post(self, out_trade_no):
        params = {'out_trade_no': out_trade_no}
        #params = {'transaction_id': out_trade_no}
        self.set_params(params=params)
        return self.post_xml_ssl()


class UnionPayNotify(UnionPay):

    def __init__(self, unionpay_config):
        super(UnionPayNotify, self).__init__(unionpay_config)

    def notify_process(self, raw_content):
        notice = self.signer.parse_arguments(raw_content.decode('utf-8'))

        try:
            self.signer.validate(notice)
        except crypto.Error as errors:
            print('UnionPay notify validation failed: ' + str(errors))
            response = {}
            response['respCode'] = '422'
            response['respMsg'] = str(errors)
            return response

        return notice

class UnionPayCloseOrder(UnionPay):

    def __init__(self, unionpay_config):
        super(UnionPayCloseOrder, self).__init__(unionpay_config)
        self.url = 'https://api.mch.weixin.qq.com/pay/closeorder'

    def post(self, out_trade_no):
        params = {'out_trade_no': out_trade_no}
        self.set_params(params=params)
        return self.post_xml_ssl()

class Refund(UnionPay):

    def __init__(self, unionpay_config):
        super(Refund, self).__init__(unionpay_config)
        self.url = 'https://api.mch.weixin.qq.com/secapi/pay/refund'

    def post(self, out_trade_no, out_refund_no, total_fee, refund_fee):
        params = {'out_trade_no': out_trade_no,
                  'out_refund_no': out_refund_no,
                  'total_fee': total_fee,
                  'refund_fee': refund_fee,
                  'op_user_id': self.mch_id}
        self.set_params(**params)
        return self.post_xml_ssl()


class RefundQuery(UnionPay):

    def __init__(self, unionpay_config):
        super(RefundQuery, self).__init__(unionpay_config)
        self.url = 'https://api.mch.weixin.qq.com/pay/refundquery'

    def post(self, out_refund_no):
        params = {'out_refund_no': out_refund_no}
        self.set_params(**params)
        return self.post_xml()


class DownloadBill(UnionPay):

    def __init__(self, unionpay_config):
        super(DownloadBill, self).__init__(unionpay_config)
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


class UnionPaySigner(object):

    def __init__(self, pfx_filepath, password, x509_filepath, digest_method='sha1', **kwargs):
        '''
        @pfx_filepath:      pfx file path
        @password:          pfx pem password
        @x509_filepath:     x509 file path
        @digest_method:     default digest method is sha1
        '''
        self.digest_method = digest_method
        self.PKCS12 = self.loadPKCS12(pfx_filepath, password)
        self.X509 = self.loadX509(x509_filepath)

    @classmethod
    def getSigner(cls, config):
        '''
        @config: unionpay config object
        '''
        signer = cls(
            config.pfx_file,
            config.password,
            config.x509_file,
            config.digest_method
        )
        return signer

    @staticmethod
    def loadPKCS12(filepath, password):
        '''
        @filepath: the pfx file path
        @password: the password of pfx file
        '''
        f = open(filepath, 'rb').read()
        return crypto.load_pkcs12(f, password)

    @staticmethod
    def loadX509(filepath, filetype=FILETYPE_PEM):
        '''
        @filepath: the cert file path
        @password: the cert type
        '''
        f = open(filepath, 'rb').read()
        return crypto.load_certificate(filetype, f)

    @staticmethod
    def simple_urlencode(params, sort=True):
        '''
        @params: a map type will convert to url args
        @sort: if sorted method will used to sort params
        '''
        data = UnionPaySigner.filter_params(params)
        items = sorted(
            data.items(), key=lambda d: d[0]) if sort else data.items()

        results = []
        for item in items:
            results.append("%s=%s" % (item[0], item[1]))
        s = '&'.join(results)
        return s.encode('utf-8')

    @staticmethod
    def parse_arguments(raw):
        '''
        @raw: raw data to parse argument
        '''
        data = {}
        qs_params = parse_qs(str(raw))
        for name in qs_params.keys():
            data[name] = qs_params.get(name)[-1]
        return data

    @staticmethod
    def filter_params(params):
        '''
        Remove None or empty argments
        '''
        if not params:
            return dict()

        cp_params = params.copy()
        for key in params.keys():
            value = cp_params[key]
            if value is None or len(str(value)) == 0:
                cp_params.pop(key)
        return cp_params

    @staticmethod
    def sign_by_soft(private_key, sign_digest, digest_method='sha1'):
        '''
        @private_key: the private_key get from PKCS12 pem
        @sign_digest: the hash value of urlencoded string
        @digest_method: the unionpay using sha1 digest string
        '''
        return crypto.sign(private_key, sign_digest, digest_method)

    def sign(self, data):
        '''
        @data: a dict ready for sign, should not contain "signature" key name
        Return base64 encoded signature and set signature to data argument
        '''

        cert_id = self.PKCS12.get_certificate().get_serial_number()
        data['certId'] = str(cert_id)
        string_data = self.simple_urlencode(data)
        sign_digest = sha1(string_data).hexdigest()
        private_key = self.PKCS12.get_privatekey()
        soft_sign = self.sign_by_soft(
            private_key, sign_digest, self.digest_method)
        base64sign = base64.b64encode(soft_sign)
        data['signature'] = base64sign.decode('utf-8')
        return base64sign

    def validate(self, data):
        '''
        @data: a dict ready for validate, must contain "signature" key name
        '''
        signature_orignal = data.pop('signature')
        signature_string = signature_orignal.replace(' ', '+')
        signature_bytes = signature_string.encode('utf-8')
        signature = base64.b64decode(signature_bytes)

        if 'fileContent' in data and data['fileContent']:
            file_content = data['fileContent'].replace(' ', '+')
            data.update(fileContent=file_content)
        stringData = self.simple_urlencode(data)
        digest = sha1(stringData).hexdigest()

        #print('---------------------')
        #print('verify signature')
        #print(signature)
        #print(data)
        #print(stringData)
        #print(digest)
        #print('---------------------')

        # calc signature
        crypto.verify(self.X509, signature, digest, self.digest_method)

    @staticmethod
    def accept_filetype(f, merchant_id):
        '''
        @f:             filename
        @merchant_id:   merchant id    
        '''
        res = False
        if (TradeFlowType.Normal in f
                or TradeFlowType.Error in f
                or TradeFlowType.Periodic in f
                or TradeFlowType.PeriodicError in f) and f.endswith(merchant_id):
            res = True
        return res

    @staticmethod
    def save_file_data(settle_date, data, temp_path, merchant_id, temp_prefix='unionpay_'):
        '''
        @settle_date:   like 1216 for generate filename
        @data:          fileContent from request
        @temp_path:     save data to a temp path

        '''
        timeRandomString = datetime.now().strftime("%Y%m%d%H%M%S")
        path = os.path.join(
            temp_path, "%s%s%s" % (temp_prefix, datetime.now().year, settle_date))

        if not os.path.exists(path):
            os.mkdir(path)

        fileWholePath = "%s/SMT_%s.zip" % (path, timeRandomString)
        with open(fileWholePath, 'wb') as f:
            f.write(data)
        logger.debug("temp file <%s> createdï¼" % fileWholePath)
        zfile = ZipFile(fileWholePath, 'r')
        zfile.extractall(path)
        files_list = zfile.infolist()
        logger.debug("file <%s> unzipedï¼" % ','.join(zfile.namelist()))
        zfile.close()
        logger.debug("balance file <%s> saved!" % path)
        os.unlink(fileWholePath)
        logger.debug("temp file deleted")

        balance_files = []

        for item in files_list:
            if Signer.accept_filetype(item.filename, merchant_id):
                balance_files.append(os.path.join(path, item.filename))
        return balance_files

    @staticmethod
    def reader_file_data(files_list, settle_date):
        insert_params = []
        for item in files_list:
            Signer.parse_line(settle_date, item, insert_params)

        return insert_params

    @staticmethod
    def parse_line(settle_date, item, params_list):
        with open(item, 'rb') as f:
            for field in f.readlines():
                line = LineObject(field)
                params = {
                    'settle_date': settle_date,
                    'txnType': line.txnType,
                    'orderId': line.orderId,
                    'queryId': line.queryId,
                    'txnAmt': line.txnAmt,
                    'merId': line.merId,
                    'data': field
                }
                params_list.append(params)

