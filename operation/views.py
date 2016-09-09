from datetime import datetime, timedelta
import pytz
from pytz import timezone
from collections import OrderedDict

from django.shortcuts import render

from rest_framework import status
from rest_framework.decorators import (
    api_view, authentication_classes, permission_classes
)
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.parsers import JSONParser, FileUploadParser, MultiPartParser, FormParser

from parking.models import ParkingLot, VehicleIn, VehicleOut
from parking.serializers import (
    VehicleInSerializer, VehicleOutSerializer, ParkingLotSerializer
)
from userprofile.models import Role, ParkingLotGroup, OperatorProfile

from billing.models import OfflinePayment, Bill, PrePayOrder
from billing.serializers import OfflinePaymentSerializer

# Create your views here.
import logging
logger = logging.getLogger(__name__)

RESULTS     = 40
MAX_RESULTS = 100
MAX_TIMESPAN = 30 # minutes
MAX_QUERY_DAYS = 30

parkinglot_connected = []

@api_view(['GET'])
@permission_classes((IsAuthenticated,))
def vehicle_in_api(request):

    user = request.user
    lots = get_parking_lots(user)

    id = request.GET.get('id')
    parking_lot_id = request.GET.get('parking_lot_id')
    plate_number = request.GET.get('plate_number')
    start_index = request.GET.get('start_index')
    max_results = request.GET.get('max_results')

    m = RESULTS
    v_ins = None

    if max_results:
        m = int(max_results)
        if m > MAX_RESULTS:
            m = MAX_RESULTS
        if m < 0:
            m = RESULTS

    now = datetime.now(pytz.utc)    
    before = now + timedelta(days=-7)
    before_str = before.strftime('%Y-%m-%d %H:%M:%S')

    try:
        if parking_lot_id:
            v_ins_all = VehicleIn.objects.filter(parking_lot_id=parking_lot_id).filter(in_time__gt=before_str).order_by('-in_time')
            total = v_ins_all.count()
        elif plate_number:
            pn = plate_number[-6:] # only match last 6 digits/chatacters
            v_ins_all = VehicleIn.objects.filter(plate_number__contains=pn).filter(in_time__gt=before_str).order_by('-in_time')
        else:
            v_ins_all = VehicleIn.objects.filter(in_time__gt=before_str).order_by('-in_time')
            total = v_ins_all.count()
        if id:
            #v_ins = VehicleIn.objects.filter(pk=id)
            v_ins = v_ins_all.filter(pk=id)
        elif start_index:
            start = int(start_index)
            if start < 0:
                start = 0
            end = start + m
            v_ins = v_ins_all[start:end]
        else:
            v_ins = v_ins_all[:m]

    except VehicleIn.DoesNotExist:
        logger.error('Can not find vehicle-in records.')

    if v_ins:
        serializer = VehicleInSerializer(v_ins,many=True)
        data = serializer.data
        for i in data:
            try:
                lot = ParkingLot.objects.get(id=i['parking_lot'])
                i['parking_lot'] = lot.name
            except ParkingLot.DoesNotExist:
                logger.error('Can not find parking lot has id[%d' % i.parking_lot)
                i['parking_lot'] = ''

        logger.info('Vehicle-in records. Total[%d]' % len(data))
    else:
        data = {'detail': 'No vehicle-in record.'}
        logger.info(data)

    origin = request.META.get('HTTP_ORIGIN')
    if origin:
        logger.info('origin[' + origin + ']')

    response = Response(data)
    response['Access-Control-Allow-Credentials'] = 'true'
    if origin:
        response['Access-Control-Allow-Origin'] = origin
    else:
        response['Access-Control-Allow-Origin'] = '*'
    return response
    #return Response(serializer.data)

@api_view(['GET'])
@permission_classes((IsAuthenticated,))
def vehicle_out_api(request):
    id = request.GET.get('id')
    parking_lot_id = request.GET.get('parking_lot_id')
    plate_number = request.GET.get('plate_number')
    start_index = request.GET.get('start_index')
    max_results = request.GET.get('max_results')

    m = RESULTS
    v_outs = None

    if max_results:
        m = int(max_results)
        if m > MAX_RESULTS:
            m = MAX_RESULTS
        if m < 0:
            m = RESULTS

    now = datetime.now(pytz.utc)
    #before = datetime(now.year,now.month,now.day-7)
    before = now + timedelta(days=-7)
    before_str = before.strftime('%Y-%m-%d %H:%M:%S')

    try:
        if parking_lot_id:
            v_outs_all = VehicleOut.objects.filter(parking_lot_id=parking_lot_id).filter(out_time__gt=before_str).order_by('-out_time')
            total = v_outs_all.count()
        elif plate_number:
            pn = plate_number[-6:] # only match last 6 digits/chatacters
            v_outs_all = VehicleOut.objects.filter(plate_number__contains=pn).filter(out_time__gt=before_str).order_by('-out_time')
        else:
            v_outs_all = VehicleOut.objects.filter(out_time__gt=before_str).order_by('-out_time')
            total = v_outs_all.count()

        if id:
            v_outs = VehicleOut.objects.filter(pk=id)
        elif start_index:
            start = int(start_index)
            if start < 0:
                start = 0
            end = start + m
            v_outs = v_outs_all[start:end]
        else:
            v_outs = v_outs_all[:m]

    except VehicleOut.DoesNotExist:
        logger.error('Can not find vehicle-out records.')

    if v_outs:
        serializer = VehicleOutSerializer(v_outs,many=True)
        data = serializer.data
        for i in data:
            try:
                lot = ParkingLot.objects.get(id=i['parking_lot'])
                i['parking_lot'] = lot.name
            except ParkingLot.DoesNotExist:
                logger.error('Can not find parking lot has id[%d' % i.parking_lot)
                i['parking_lot'] = ''
    else:
        data = {'detail': 'No vehicle-out record.'}

    #logger.info(data)

    origin = request.META.get('HTTP_ORIGIN')
    if origin:
        logger.info('origin[' + origin + ']')

    response = Response(data)
    response['Access-Control-Allow-Credentials'] = 'true'

    if origin:
        response['Access-Control-Allow-Origin'] = origin
    else:
        response['Access-Control-Allow-Origin'] = '*'
    return response


@api_view(['GET'])
@permission_classes((IsAuthenticated,))
def offline_payment_api(request):
    user = request.user    
    parking_lot_id = request.GET.get('parking_lot_id')
    plate_number = request.GET.get('plate_number')
    start_index = request.GET.get('start_index')
    max_results = request.GET.get('max_results')

    # fill in response headers
    response = Response()
    response['Access-Control-Allow-Credentials'] = 'true'
    origin = request.META.get('HTTP_ORIGIN')

    if origin:
        logger.info('HTTP_ORIGIN[%s]' % origin)
        response['Access-Control-Allow-Origin'] = origin
    else:
        response['Access-Control-Allow-Origin'] = '*'#'ht

    # only group_user or operator_bill are allowed to perform payment query
    try:
        roles = Role.objects.filter(owner=request.user)
        role_list = []
        for r in roles:
            role_list.append(r.role)
        logger.info('Role list[%s]' % role_list)
        if 'operator_bill' not in role_list and 'group_user' not in role_list:
            logger.error('Please login as operator_bill or group_user.')
            response.data = {'detail': 'Please login as operator_bill or group_user.'}
            response.status_code = status.HTTP_403_FORBIDDEN
            return response
    except Role.DoesNotExist:
        logger.error('Cannot get role for [%s]' % str(request.user))
        response.data = {'detail': 'Please login as operator_bill or group_user.'}
        response.status_code = status.HTTP_403_FORBIDDEN
        return response

    now = datetime.now(pytz.utc)
    before = now + timedelta(days=-MAX_QUERY_DAYS)
    before_str = before.strftime('%Y-%m-%d %H:%M:%S')
    try:
        start = int(start_index)
        if start < 0:
            start = 0
    except TypeError:
        start = 0

    m = RESULTS
    if max_results:
        m = int(max_results)
        if m > MAX_RESULTS:
            m = MAX_RESULTS
        if m < 0:
            m = RESULTS
    # retrieve data from specified parking lots
    if 'group_user' in role_list:
        # get parking lot list
        logger.info('username[%s]' % user.username)
        p_list = []

        try:
            op = OperatorProfile.objects.get(user=user)
            parking_lots = op.parking_lots.all()
            for p in parking_lots:
                p_list.append(p.id)
        except OperatorProfile.DoesNotExist:
            logger.error('There is NO profile for operator[%s]' % o.username)
        
        try:

            offline_payments = OfflinePayment.objects.filter(parking_lot__in=p_list).filter(payment_time__gt=before_str).filter(id__gt=start).order_by('-payment_time')[0:m]
        except OfflinePayment.DoesNotExist:
            logger.error('No offline payment record for operator[%s]' % user.username)
    elif 'operator_bill' in role_list:
        try:            
            offline_payments = OfflinePayment.objects.filter(payment_time__gt=before_str).filter(id__gt=start).order_by('-payment_time')[0:m]
        except OfflinePayment.DoesNotExist:
            logger.error('No offline payment record for operator[%s]' % user.username)

    
    if not offline_payments:
        logger.error('No offline payment record.')       
        response_dict = OrderedDict()
        response_dict['kind'] = 'operation#offline_payments'
        response_dict['records'] = []
        response.data = response_dict
        return response

    serializer = OfflinePaymentSerializer(offline_payments,many=True)
    data = serializer.data
    logger.info("data: %s"%data)
    parking_lot_ids = list(set([i['parking_lot'] for i in serializer.data]))    
    try:            
        #lot = ParkingLot.objects.get(id=i['parking_lot'])
        parkinglots = ParkingLot.objects.filter(id__in = parking_lot_ids)
        lots_id2name = {i.id: i.name for i in parkinglots}
        for i in data: 
            i['parking_lot'] = lots_id2name[i['parking_lot']]
    except ParkingLot.DoesNotExist:
            logger.error('Can not find parking lot has id[%d' % i.parking_lot)
            i['parking_lot'] = ''    

    response_dict = OrderedDict()
    response_dict['kind'] = 'operation#offline_payments'
    response_dict['records'] = data
    response.data = response_dict

    return response
    

@api_view(['GET'])
@permission_classes((IsAuthenticated,))
def online_payment_api(request):
    user = request.user
    id = request.GET.get('id')
    parking_lot_id = request.GET.get('parking_lot_id')
    plate_number = request.GET.get('plate_number')
    start_index = request.GET.get('start_index')
    max_results = request.GET.get('max_results')

    # fill in response headers
    response = Response()
    response['Access-Control-Allow-Credentials'] = 'true'
    origin = request.META.get('HTTP_ORIGIN')

    if origin:
        logger.info('HTTP_ORIGIN[%s]' % origin)
        response['Access-Control-Allow-Origin'] = origin
    else:
        response['Access-Control-Allow-Origin'] = '*'#'ht

    # only group_user or operator_bill are allowed to perform payment query
    try:
        roles = Role.objects.filter(owner=request.user)
        role_list = []
        for r in roles:
            role_list.append(r.role)
        logger.info('Role list[%s]' % role_list)
        if 'operator_bill' not in role_list and 'group_user' not in role_list:
            logger.error('Please login as operator_bill or group_user.')
            response.data = {'detail': 'Please login as operator_bill or group_user.'}
            response.status_code = status.HTTP_403_FORBIDDEN
            return response
    except Role.DoesNotExist:
        logger.error('Cannot get role for [%s]' % str(request.user))
        response.data = {'detail': 'Please login as operator_bill or group_user.'}
        response.status_code = status.HTTP_403_FORBIDDEN
        return response

    now = datetime.now(pytz.utc)
    before = now + timedelta(days=-MAX_QUERY_DAYS)
    before_str = before.strftime('%Y-%m-%d %H:%M:%S')

    records = []

    # retrieve data from specified parking lots
    if 'group_user' in role_list:
        # get parking lot list
        logger.info('username[%s]' % user.username)
        p_list = []


        try:
            op = OperatorProfile.objects.get(user=user)
            parking_lots = op.parking_lots.all()
            for p in parking_lots:
                p_list.append(p.id)
        except OperatorProfile.DoesNotExist:
            logger.error('There is NO profile for operator[%s]' % o.username)

        try:
            online_payments = Bill.objects.filter(paid=True).filter(updated_time__gt=before_str).order_by('-updated_time')
            for p in online_payments:
                lot_id = p.vehicle_in.parking_lot_id
                if lot_id not in p_list:
                    record = OrderedDict()
                    utc_time = p.updated_time
                    local_time = utc_time.astimezone(timezone('Asia/Shanghai'))
                    local_time_str = local_time.strftime('%Y-%m-%d %H:%M:%S')
                    record['plate_number'] = p.vehicle_in.plate_number
                    record['payment_time'] = local_time_str
                    record['parking_lot'] = p.vehicle_in.parking_lot.name
                    record['amount'] = p.amount
                    records.append(record)

            #lot_name = p.vehicle_in.parking_lot.name
            #print('vehicle in id[%d], lot id[%d], name[%s]' % (p.vehicle_in_id,lot_id,lot_name))
            logger.info(records)

        except Bill.DoesNotExist:
            logger.error('No online payment record for operator[%s]' % user.username)

    elif 'operator_bill' in role_list:
        try:
            online_payments = Bill.objects.filter(paid=True).filter(updated_time__gt=before_str).order_by('-updated_time')
            for p in online_payments:
                record = OrderedDict()
                utc_time = p.updated_time
                local_time = utc_time.astimezone(timezone('Asia/Shanghai'))
                local_time_str = local_time.strftime('%Y-%m-%d %H:%M:%S')
                record['plate_number'] = p.vehicle_in.plate_number
                record['payment_time'] = local_time_str
                record['parking_lot'] = p.vehicle_in.parking_lot.name
                record['amount'] = p.amount
                records.append(record)

            #lot_name = p.vehicle_in.parking_lot.name
            #print('vehicle in id[%d], lot id[%d], name[%s]' % (p.vehicle_in_id,p.vehicle_in.parking_lot_id,lot_name))
            logger.info(records)
        except Bill.DoesNotExist:
            logger.error('No online payment record for operator[%s]' % user.username)


    response_dict = OrderedDict()
    response_dict['kind'] = 'operation#online_payments'
    response_dict['records'] = records
    response.data = response_dict

    return response

@api_view(['GET'])
@permission_classes((IsAuthenticated,))
def prepayment_api(request):
    user = request.user
    id = request.GET.get('id')
    parking_lot_id = request.GET.get('parking_lot_id')
    plate_number = request.GET.get('plate_number')
    start_index = request.GET.get('start_index')
    max_results = request.GET.get('max_results')

    # fill in response headers
    response = Response()
    response['Access-Control-Allow-Credentials'] = 'true'
    origin = request.META.get('HTTP_ORIGIN')

    if origin:
        logger.info('HTTP_ORIGIN[%s]' % origin)
        response['Access-Control-Allow-Origin'] = origin
    else:
        response['Access-Control-Allow-Origin'] = '*'#'ht

    # only group_user or operator_bill are allowed to perform payment query
    try:
        roles = Role.objects.filter(owner=request.user)
        role_list = []
        for r in roles:
            role_list.append(r.role)
        logger.info('Role list[%s]' % role_list)
        if 'operator_bill' not in role_list:
            logger.error('Please login as operator_bill.')
            response.data = {'detail': 'Please login as operator_bill.'}
            response.status_code = status.HTTP_403_FORBIDDEN
            return response
    except Role.DoesNotExist:
        logger.error('Cannot get role for [%s]' % str(request.user))
        response.data = {'detail': 'Please login as operator_bill.'}
        response.status_code = status.HTTP_403_FORBIDDEN
        return response

    now = datetime.now(pytz.utc)
    before = now + timedelta(days=-MAX_QUERY_DAYS)
    before_str = before.strftime('%Y-%m-%d %H:%M:%S')

    records = []


    # retrieve data from specified parking lots
    if 'operator_bill' in role_list:
        try:
            prepayments = PrePayOrder.objects.filter(paid=True).filter(updated_time__gt=before_str).order_by('-updated_time')
            for p in prepayments:
                record = OrderedDict()
                utc_time = p.updated_time
                local_time = utc_time.astimezone(timezone('Asia/Shanghai'))
                local_time_str = local_time.strftime('%Y-%m-%d %H:%M:%S')
                record['user_name'] = p.user.username
                record['payment_time'] = local_time_str
                record['payment_channel'] = p.payment_channel
                record['amount'] = p.amount
                records.append(record)

            #lot_name = p.vehicle_in.parking_lot.name
            #print('vehicle in id[%d], lot id[%d], name[%s]' % (p.vehicle_in_id,p.vehicle_in.parking_lot_id,lot_name))
            logger.info(records)
        except PrePayOrder.DoesNotExist:
            logger.error('No prepayment record for operator[%s]' % user.username)



    response_dict = OrderedDict()
    response_dict['kind'] = 'operation#prepayments'
    response_dict['records'] = records
    response.data = response_dict

    return response


@api_view(['POST'])
def file_upload_api(request):
    parser_classes = (JSONParser, MultiPartParser, FormParser,)
    if request.method == 'POST':

        print(request.FILES.keys())
        up_file = request.FILES['file']

        #filename = request.user
        m, ext = os.path.splitext(up_file.name)
        filename = str(request.user) + ext

        filepath = '/home/twy76/android_packages/' + filename

        print(filepath)

        destination = open(filepath, 'wb+')
        for chunk in up_file.chunks():
            destination.write(chunk)
        destination.close()

        md5 = CalcMD5('/home/twy76/android_packages/' + filename)

        filedst = '/home/twy76/android_packages/' + md5 + filename

        os.rename(filepath, filedst)

        return Response(up_file.name, status.HTTP_201_CREATED)


def get_paid_bill(vi):
    pass


@api_view(['POST'])
def parkinglot_connected_api(request):
    parser = JSONParser
    confirmed = 'no'
    data = request.data

    try:
        identifier = str(data['identifier'])
        ip_address = data.get('ip_address')
    except KeyError as e:
        detail = {'detail': repr(e)}
        logger.error(detail)
        return Response(detail, status=status.HTTP_406_NOT_ACCEPTABLE)

    # verify the entrance
    try:
        #print('en[%s]' % en)
        lot = ParkingLot.objects.get(identifier=identifier)
    except ParkingLot.DoesNotExist as e:
        # for debug
        #pl = ParkingLot.objects.get(pk=5)
        #er = Entrance(name=en,parking_lot=pl)
        #er.save()
        detail = {'detail': repr(e)}
        logger.error(detail)
        return Response(detail, status=status.HTTP_406_NOT_ACCEPTABLE)
    data = ParkingLotSerializer(lot).data
    data['ip_address'] = ip_address
    data['updated_time'] = datetime.now(pytz.utc)
    parkinglot_connected.append(data)
    logger.info('Parking lot[%s] connected.' % lot.name)
    logger.debug(lot)
    return Response({'success':'connected'})

@api_view(['POST'])
def parkinglot_disconnected_api(request):
    return Response({'success':'disconnected'})

@api_view(['GET'])
def parkinglot_online_api(request):
    parking_lots = []
    try:
        lots = ParkingLot.objects.all()
    except ParkingLot.DoesNotExist:
        detail = {'detail': repr(e)}
        logger.error(detail)
        return Response(detail, status=status.HTTP_406_NOT_ACCEPTABLE)

    data = ParkingLotSerializer(lots,many=True).data

    for d in data:
        # vehicle-in record
        # vehicle-out record
        # offline payment record
        try:
            v_in = VehicleIn.objects.filter(parking_lot=d['id']).latest('created_time')
            v_out = VehicleOut.objects.filter(parking_lot=d['id']).latest('created_time')
            off_pay = OfflinePayment.objects.filter(parking_lot=d['id']).latest('created_time')
        except Exception as exc:
            continue

        now = datetime.now(pytz.utc)
        diff_in = int((now - v_in.created_time).total_seconds()/60)
        diff_out = int((now - v_out.created_time).total_seconds()/60)
        diff_pay = int((now - off_pay.created_time).total_seconds()/60)

        if diff_in < MAX_TIMESPAN or diff_out < MAX_TIMESPAN and diff_pay < MAX_TIMESPAN:
            d['time_to_latest_record'] = diff_in
            parking_lots.append(d)
        print('most likely time span[%d], parking lot[%s]' % (diff_in,d['name']))

    return Response({'parkinglots': parking_lots})


def get_roles(user):
    role_list = []
    try:
        roles = Role.objects.filter(owner=request.user)
        for r in roles:
            role_list.append(r.role)
        logger.info('Role is[%s]' % roles)
        if len(role_list) > 0:
            content['role'] = role_list
    except Role.DoesNotExist:
        pass

    return role_list

def get_groups(user):
    try:
        g = user.parkinglotgroup_set.all()
    except ParkingLotGroup.DoesNotExist:
        pass
    return g

def get_parking_lots(user):
    parking_lots = []
    try:
        groups = user.parkinglotgroup_set.all()
        for g in groups:
            lots = g.parking_lot.all()
            for l in lots:
                parking_lots.append(l)
    except ParkingLotGroup.DoesNotExist:
        pass
    except ParkingLot.DoesNotExist:
        pass

    return parking_lots

