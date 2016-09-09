from django.shortcuts import render
from django.contrib.auth import logout as auth_logout
from django.contrib.auth import authenticate, login
from django.contrib.auth.models import User

#import simplejson
import random
import pytz
import base64
import binascii

from collections import OrderedDict
from datetime import datetime

from rest_framework import status
from rest_framework.decorators import (
    api_view, authentication_classes, permission_classes
)
from rest_framework.response import Response
from rest_framework.authentication import (
    SessionAuthentication, BasicAuthentication,
    get_authorization_header
)
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import JSONParser

from yuntongxun_sms.CCP_REST_DEMO_Python_v2_7r.DEMO.SendTemplateSMS import sendTemplateSMS

from userprofile.models import Vehicle, UserProfile, Role, OperatorProfile
from userprofile.serializers import RoleSerializer
from account.models import VerificationCode
from parking.models import ParkingLot

import logging
logger = logging.getLogger(__name__)

# pre-defined roles
ROLES = ['operator_parkinglot', 'operator_group_user', 'operator_bill',
         'operator_end_user', 'operator_app', 'group_user']

# Create your views here.
def basic_challenge(realm = None):
    if realm is None:
        realm = 'api'
    response =  Response({'detail': 'Authorization Required'})
    response['WWW-Authenticate'] = 'Basic realm="%s"' % (realm)
    response.status_code = 401
    return response

#@csrf_exempt
@api_view(['GET', 'POST', 'OPTIONS'])
#@authentication_classes((BasicAuthentication,SessionAuthentication))
#@permission_classes((IsAuthenticated,))
def web_login_api(request):
    credential = False
    logger.debug(request.META)

    origin = request.META.get('HTTP_ORIGIN')
    #access_control_request_method = request.META.get('Access-Control-Request-Method')
    #access_control_request_headers = request.META.get('Access-Control-Request-Headers')

    if request.method == 'OPTIONS':
        response = Response({'detail': 'options request'})
        response['Access-Control-Allow-Origin'] = origin
        response['Access-Control-Request-Method'] = 'GET, POST, OPTIONS'#access_control_request_method
        response['Access-Control-Request-Headers'] = 'Content-Type, Authorization'
        response['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
        if origin:
            logger.info('HTTP_ORIGIN[%s]' % origin)
            response['Access-Control-Allow-Origin'] = origin
        else:
            response['Access-Control-Allow-Origin'] = '*'#'http://192.168.1.137:8000'

        return response

    auth = get_authorization_header(request).split()

    if not auth or auth[0].lower() != b'basic':
        error = 'No basic header. No credentials provided.'

    if len(auth) == 1:
        error = 'Invalid basic header. No credentials provided.'
    elif len(auth) > 2:
        error = 'Invalid basic header. Credentials string should not contain spaces.'


    logger.info(auth)

    try:
        auth_parts = base64.b64decode(auth[1]).decode('utf-8').partition(':')
        credential = True
    except (TypeError, UnicodeDecodeError, binascii.Error, Exception):
        error = 'Invalid basic header. Credentials not correctly base64 encoded.'
    else:
        error = 'Invalid basic header. Credentials not correctly base64 encoded.'

    if not credential:
        return Response({'detail': error},status=status.HTTP_401_UNAUTHORIZED)

    logger.info(auth_parts)

    username = auth_parts[0]
    password = auth_parts[2]
    user = authenticate(username = username, password = password)

    if user is None:
        return Response({'detail': 'Authentication credentials were not provided.'},status=status.HTTP_403_FORBIDDEN)
        return basic_challenge()
    else:
        login(request, user)

    #user = authenticate(username=username, password=password)
    logger.info('User logged in[' + str(request.user) +']')
    content = {
        'user': str(request.user),  # `django.contrib.auth.User` instance.
        'auth': str(request.auth),  # None
    }
    try:
        roles = Role.objects.filter(owner=request.user)
        role_list = []
        for r in roles:
            role_list.append(r.role)
        logger.info('Role is[%s]' % roles)
        if len(role_list) > 0:
            content['role'] = role_list
    except Role.DoesNotExist:
        logger.error('Cannot get role for [%s]' % str(request.user))
        pass

    response = Response(content)

    XS_SHARING_ALLOWED_HEADERS = ['Content-Type', 'AUTHORIZATION', '*']
    response['Access-Control-Allow-Headers'] = ",".join(XS_SHARING_ALLOWED_HEADERS)
    response['Access-Control-Allow-Credentials'] = 'true'

    origin = request.META.get('HTTP_ORIGIN')

    if origin:
        logger.info('HTTP_ORIGIN[%s]' % origin)
        response['Access-Control-Allow-Origin'] = origin
    else:
        response['Access-Control-Allow-Origin'] = 'http://192.168.1.137:8000'
    return response

    return Response(content)

@api_view(['GET', 'POST'])
@authentication_classes((SessionAuthentication, BasicAuthentication))
@permission_classes((IsAuthenticated,))
def login_api(request, format=None):
    logger.info('User logged in[' + str(request.user) +']')
    content = {
        'user': str(request.user),  # `django.contrib.auth.User` instance.
        'auth': str(request.auth),  # None
    }
    try:
        roles = Role.objects.filter(owner=request.user)
        role_list = []
        for r in roles:
            role_list.append(r.role)
        logger.info('Role is[%s]' % roles)
        if len(role_list) > 0:
            content['role'] = role_list
    except Role.DoesNotExist:
        logger.error('Cannot get role for [%s]' % str(request.user))
        pass

    response = Response(content)

    XS_SHARING_ALLOWED_HEADERS = ['Content-Type', 'AUTHORIZATION', '*']
    response['Access-Control-Allow-Headers'] = ",".join(XS_SHARING_ALLOWED_HEADERS)
    response['Access-Control-Allow-Credentials'] = 'true'

    origin = request.META.get('HTTP_ORIGIN')
    #logger.info(request.META)

    if origin:
        logger.info('HTTP_ORIGIN[%s]' % origin)
        response['Access-Control-Allow-Origin'] = origin
    else:
        response['Access-Control-Allow-Origin'] = 'http://192.168.1.137:8000'
    return response
 
    return Response(content)

@api_view(['GET', 'POST'])
def logout_api(request):
    auth_logout(request)
    return Response({"success": "Successfully logged out."})
                    #status=status.HTTP_200_OK)


@api_view(['DELETE', 'GET', 'OPTIONS', 'POST', 'PUT',])
#@permission_classes((IsAuthenticated,))
def operator_api(request):
    """
    app api
    """
    credential = False
    logger.debug(request.META)

    origin = request.META.get('HTTP_ORIGIN')
    #access_control_request_method = request.META.get('Access-Control-Request-Method')
    #access_control_request_headers = request.META.get('Access-Control-Request-Headers')

    if request.method == 'OPTIONS':
        response = Response({'detail': 'options request'})
        response['Access-Control-Allow-Origin'] = origin
        response['Access-Control-Request-Method'] = 'DELETE, GET, POST, PUT, OPTIONS'#access_control_request_method
        response['Access-Control-Request-Headers'] = 'Content-Type, Authorization'
        response['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
        if origin:
            logger.info('HTTP_ORIGIN[%s]' % origin)
            response['Access-Control-Allow-Origin'] = origin
        else:
            response['Access-Control-Allow-Origin'] = '*'#'http://192.168.1.137:8000'

        return response

    auth = get_authorization_header(request).split()

    if not auth or auth[0].lower() != b'basic':
        error = 'No basic header. No credentials provided.'

    if len(auth) == 1:
        error = 'Invalid basic header. No credentials provided.'
    elif len(auth) > 2:
        error = 'Invalid basic header. Credentials string should not contain spaces.'


    logger.info(auth)

    try:
        auth_parts = base64.b64decode(auth[1]).decode('utf-8').partition(':')
        credential = True
    except (TypeError, UnicodeDecodeError, binascii.Error, Exception):
        error = 'Invalid basic header. Credentials not correctly base64 encoded.'
    else:
        error = 'Invalid basic header. Credentials not correctly base64 encoded.'


    if not credential:
        return Response({'detail': error},status=status.HTTP_401_UNAUTHORIZED)

    logger.info(auth_parts)

    username = auth_parts[0]
    password = auth_parts[2]
    user = authenticate(username = username, password = password)

    if user is None:
        return Response({'detail': 'Authentication credentials were not provided.'},status=status.HTTP_403_FORBIDDEN)
        return basic_challenge()
    else:
        login(request, user)

    #user = authenticate(username=username, password=password)
    logger.info('User logged in[' + str(request.user) +']')
    content = {
        'user': str(request.user),  # `django.contrib.auth.User` instance.
        'auth': str(request.auth),  # None
    }
    try:
        roles = Role.objects.filter(owner=request.user)
        role_list = []
        for r in roles:
            role_list.append(r.role)
        logger.info('Role is[%s]' % roles)
        if len(role_list) > 0:
            content['role'] = role_list
    except Role.DoesNotExist:
        logger.error('Cannot get role for [%s]' % str(request.user))
        pass






    parser = JSONParser
    confirmed = 'no'
    data = request.data
    #user = request.user

    # fill in response headers
    response = Response()
    response['Access-Control-Allow-Credentials'] = 'true'
    origin = request.META.get('HTTP_ORIGIN')

    if origin:
        logger.info('HTTP_ORIGIN[%s]' % origin)
        response['Access-Control-Allow-Origin'] = origin
    else:
        response['Access-Control-Allow-Origin'] = '*'#'ht

    if request.method == 'OPTIONS':
        response = Response({'detail': 'options request'})
        #response['Access-Control-Allow-Origin'] = origin
        response['Access-Control-Request-Method'] = 'GET, POST, PUT, DELETE, OPTIONS'#access_control_request_method
        response['Access-Control-Request-Headers'] = 'Content-Type, Authorization'
        response['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
        #if origin:
        #    logger.info('HTTP_ORIGIN[%s]' % origin)
        #    response['Access-Control-Allow-Origin'] = origin
        #else:
        #    response['Access-Control-Allow-Origin'] = '*'#'http://192.168.1.137:8000'

        return response


    # only administrator is allowed to manipulate operator account
    try:
        roles = Role.objects.filter(owner=request.user)
        role_list = []
        for r in roles:
            role_list.append(r.role)
        logger.info('Role list[%s]' % role_list)
        if 'administrator' not in role_list:
            logger.error('Please login as administrator')
            response.data = {'detail': 'Please login as administrator'}
            response.status_code = status.HTTP_403_FORBIDDEN
            return response
    except Role.DoesNotExist:
        logger.error('Cannot get role for [%s]' % str(request.user))
        response.data = {'detail': 'Please login as administrator'}
        response.status_code = status.HTTP_403_FORBIDDEN
        return response

    # remove an operator
    if request.method == 'DELETE':
        operator_name = data.get('operator_name')

        if not operator_name:
            response.data = {'detail': 'Please provide the operator account name.'}
            response.status_code = status.HTTP_406_NOT_ACCEPTABLE
            return response

        try:
            operator = User.objects.get(username=operator_name)
        except User.DoesNotExist:
            response.data = {'detail': 'Please provide a valid operator account name.'}
            response.status_code = status.HTTP_406_NOT_ACCEPTABLE
            return response

        try:
            roles = Role.objects.filter(owner=operator)
            for r in roles:
                r.owner.remove(operator)
                r.save()
                logger.info('Removed [%s] from role[%s].' % (operator.username, r.role))
        except Role.DoesNotExist:
            logger.error('There is no role assigned to the user[%s]' % operator.username)

        try:
            op = OperatorProfile.objects.get(user=operator)
        except OperatorProfile.DoesNotExist:
            logger.error('There is no operator profile for[%s].' % operator.username)


        op.delete()
        operator.delete()
        logger.info('Operator profile deleted[%s]' % operator_name)
        logger.info('Operator account deleted[%s[' % operator_name)

        response.data = {'success': 'successfully deleted operator[%s]' % operator_name}
        return response

    # query operators
    elif request.method == 'GET':
        operator_list = []

        for r in ROLES:
            try:
                role = Role.objects.get(role=r)
                logger.info(role.role)
                # get all members
                try:
                    operators = role.owner.all()

                    for o in operators:
                        operator = OrderedDict()
                        operator['operator_name'] = o.username
                        operator['role'] = role.role
                        try:
                            op = OperatorProfile.objects.get(user=o)
                            operator['description'] = op.description
                            parking_lots = op.parking_lots.all()
                            p_list = []
                            for p in parking_lots:
                                p_list.append(p.id)
                            operator['parking_lots'] = p_list
                        except OperatorProfile.DoesNotExist:
                            logger.error('There is NO profile for operator[%s]' % o.username)
                        operator_list.append(operator)
                except Role.DoesNotExist:
                    logger.info('No operator as role[%s]' % role.role)
            except Role.DoesNotExist:
                logger.info('No role[%s] account yet.' % r)

        logger.info(operator_list)

        response_dict = OrderedDict()
        response_dict['kind'] = 'operator#base_info'
        response_dict['operators'] = operator_list
        response.data = response_dict
        return response

    # add an operator
    elif request.method == 'POST':
        operator_name = data.get('operator_name')
        role_name = data.get('role')
        description = data.get('description')
        parking_lots = data.get('parking_lots')
        if not parking_lots:
            parking_lots = []

        if not operator_name:
            response.data = {'detail': 'Please provide operator account name.'}
            response.status_code = status.HTTP_406_NOT_ACCEPTABLE
            return response

        if role_name not in ROLES:
            response.data = {'detail': 'Please provide a valid role.'}
            response.status_code = status.HTTP_406_NOT_ACCEPTABLE
            return response

        # check if user name existed
        try:
            operator = User.objects.get(username=operator_name)
            response.data = {'detail': 'User name already existed.'}
            response.status_code = status.HTTP_406_NOT_ACCEPTABLE
            return response
        except User.DoesNotExist:
            pass

        operator = User()
        operator.username = operator_name
        operator.is_staff = True
        operator.set_password(operator_name)
        operator.save()

        role = Role.objects.get_or_create(role=role_name)[0]
        role.owner.add(operator)
        role.save()

        op = OperatorProfile.objects.get_or_create(user=operator)[0]
        if description:
            op.description = description

        for p in parking_lots:
            try:
                lot = ParkingLot.objects.get(id=p)
                op.parking_lots.add(lot)
                logger.info('Added parking lot[%s] for [%s].' % (lot.name, operator.username))
            except ParkingLot.DoesNotExist:
                logger.error('No parking lot has id[%d]' % p)
                next
            except ValueError:
                logger.error('Can not parse parking lot id[%s]' % p)
                next

        op.save()
        logger.info('new operator profile created[%s]' % operator.username)

        response.data = {'success': 'successfully added operator[%s]' % operator.username}
        return response

    # update an operator
    elif request.method == 'PUT':
        operator_name = data.get('operator_name')
        role_name = data.get('role')
        description = data.get('description')
        parking_lots = data.get('parking_lots')
        if not parking_lots:
            parking_lots = []

        if not operator_name:
            response.data = {'detail': 'Please provide the operator account name.'}
            response.status_code = status.HTTP_406_NOT_ACCEPTABLE
            return response

        if role_name not in ROLES:
            response.data = {'detail': 'Please provide a valid role.'}
            response.status_code = status.HTTP_406_NOT_ACCEPTABLE
            return response

        # check if user name existed
        try:
            operator = User.objects.get(username=operator_name)
        except User.DoesNotExist:
            response.data = {'detail': 'Please provide a valid operator account name.'}
            response.status_code = status.HTTP_406_NOT_ACCEPTABLE
            return response

        # update role
        try:
            roles = Role.objects.filter(owner=operator)
            # remove all roles
            for r in roles:
                r.owner.remove(operator)
                r.save()
            # assigned a role
            role = Role.objects.get_or_create(role=role_name)[0]
            role.owner.add(operator)
            role.save()
            logger.info('Role is[%s]' % role_name)
        except Role.DoesNotExist:
            logger.error('User[%s] is not an operator.' % operator_name)
            response.status_code = status.HTTP_406_NOT_ACCEPTABLE
            return response

        # update profile
        try:
            op = OperatorProfile.objects.get(user=operator)
        except OperatorProfile.DoesNotExist:
            logger.error('There is no operator profile for[%s].' % operator.username)
            op = OperatorProfile.objects.get_or_create(user=operator)[0]
            logger.info('new operator profile created[%s]' % operator)

        if description:
            op.description = description

        # update parking lot list
        if parking_lots:
            try:
                lots = op.parking_lots.all()
                for p in lots:
                    op.parking_lots.remove(p)
            except ParkingLot.DoesNotExist:
                logger.error('Failed to get parking lot id list')

            for p in parking_lots:
                try:
                    lot = ParkingLot.objects.get(id=p)
                    op.parking_lots.add(lot)
                    logger.info('Added parking lot[%s] for [%s].' % (lot.name, operator.username))
                except ParkingLot.DoesNotExist:
                    logger.error('No parking lot has id[%d]' % p)
                    next
                except ValueError:
                    logger.error('Can not parse parking lot id[%s]' % p)
                    next

        op.save()
        logger.info('Operator profile updated[%s]' % operator.username)

        response.data = {'success': 'successfully updated operator[%s]' % operator.username}
        return response


# get verification code
@api_view(['GET', 'POST'])
def verify_api(request):
    phone_number = request.GET.get('phone_number')
    #plate_number = request.GET.get('plate_number')

    #print(plate_number)
    # check phone number
    ret, error_msg = phone_number_check(phone_number)
    if not ret:
       return Response(error_msg, status=status.HTTP_400_BAD_REQUEST)

    # if the phone number is already registed
    # register and reset password
    #try:
    #    user = User.objects.get(username=phone_number)

    #    error_detail = {"detail":
    #                    "The phone number is already registed."}
    #    return Response(error_detail, status=status.HTTP_406_NOT_ACCEPTABLE)

    #except User.DoesNotExist:
        # it's ok
    #    pass


    # plate_number check
    #try:
    #    pn = Vehicle.objects.get(plate_number=plate_number)

    #    error_detail = {"detail":
    #                    "The plate number is already registed."}

    #    return Response(error_detail, status=status.HTTP_406_NOT_ACCEPTABLE)

    #except Vehicle.DoesNotExist:
        # it's ok
    #    pass


    # create a verification code fot this phine number
    try:
        p =  VerificationCode.objects.get(phone_number=phone_number)
        p.delete()

    except VerificationCode.DoesNotExist:
        # it's ok
        pass

    code = create_verification_code()

    result = sendTemplateSMS(phone_number, [code, '10'], 52368)

    print(result)

    for k,v in result.items():
        if k == 'statusCode':
            statusCode = v

    if statusCode == '000000':
        p = VerificationCode()
        p.phone_number = phone_number
        p.verification_code = code
        p.created_time = datetime.now(pytz.utc)
        p.save()

        return Response({"success": "Successfully sent SMS."})
    else:
        return Response(result, status=status.HTTP_403_FORBIDDEN)



def create_verification_code():
    chars=['0','1','2','3','4','5','6','7','8','9']
    x = random.choice(chars), random.choice(chars),random.choice(chars), random.choice(chars),random.choice(chars), random.choice(chars)
        #random.choice(chars), random.choice(chars),
        #random.choice(chars), random.choice(chars),
    code = "".join(x)

    print(code)

    return code


def phone_number_check(s):
    ret = False
    error_detail = {}
    # 3 digits prefix
    phoneprefix=['130','131','132','133','134','135','136','137','138','139',
                 '150','151','152','153','155','156','157','158','159',
                 '170','176','177','178',
                 '180','181','182','183','184','185','186','187','188','189']

    # lenth of the number should be 11
    if len(str(s)) != 11:
        error_detail['detail'] = "The length of phone number should be 11."
    else:
        # should all be digits
        if  s.isdigit():
        # check the prefix
            if s[:3] in phoneprefix:
                error_detail['detail'] = "The phone number is valid."
                ret = True
            else:
                error_detail['detail'] = "The phone number is invalid."
        else:
            error_detail['detail'] = "The phone number should all be digits."

    return ret, error_detail


@api_view(['POST'])
def register_api(request):
    #mobile = request.data.get('phone_number')
    parser = JSONParser
    confirmed = 'no'
    data = request.data
    print(request.data)

    #return Response({"success": "Successfully parsered."})


    try:
        phone_number = data['phone_number']
    #password = request.GET.get('password')
        plate_number = data['plate_number']
        verification_code = data['verification_code']
        #confirmed = request.GET.get('confirmed')
    except KeyError as e:
        error_detail = {"detail": repr(e)}
        return Response(error_detail, status=status.HTTP_406_NOT_ACCEPTABLE)

    #return Response({"success": "Successfully parsered."})


    # check verification code
    try:
        vc = VerificationCode.objects.get(phone_number=phone_number)

        time_diff = datetime.now() - vc.created_time.replace(tzinfo=None)
        if int(time_diff.total_seconds()) > 600:
            vc.delete()

            error_detail = {"detail":
                            "Verification code has expired."}

            return Response(error_detail, status=status.HTTP_404_NOT_FOUND)

        if vc.verification_code != verification_code:
            error_detail = {"detail":
                            "Verification code is invalid."}

            return Response(error_detail, status=status.HTTP_406_NOT_ACCEPTABLE)

    except VerificationCode.DoesNotExist:
        error_detail = {"detail":
                        "Please wait a moment or re-enter verification code."}

        return Response(error_detail, status=status.HTTP_404_NOT_FOUND)


    # plate_number check
    try:
        v = Vehicle.objects.get(plate_number=plate_number)

        if confirmed != 'yes':
            error_detail = {"detail":
                            "The plate number is already registed."}

            return Response(error_detail, status=status.HTTP_406_NOT_ACCEPTABLE)

    except Vehicle.DoesNotExist:
        v = Vehicle()
        v.plate_number = plate_number


    # phone number check
    try:
        user = User.objects.get(username=phone_number)

        error_detail = {"detail":
                        "The phone number is already registed."}
        return Response(error_detail, status=status.HTTP_406_NOT_ACCEPTABLE)

    except User.DoesNotExist:
        # it's ok
        pass


    user = User()
    user.username = phone_number
    user.is_staff = True
    user.save()

    up = UserProfile.objects.get_or_create(user=user)[0]
    up.account_balance = 1000
    up.save()
    print("new user profile created")

    v.save()
    v.owner.add(user)
    #user.save()
    #pn.save()

    return Response({"success": "Successfully registered."})

@api_view(['POST'])
def reset_password_api(request):
    data = request.data
    print(request.data)

    #return Response({"success": "Successfully parsered."})


    try:
        phone_number = data['phone_number']
    #password = request.GET.get('password')
        password = data['password']
        verification_code = data['verification_code']
        #confirmed = request.GET.get('confirmed')
    except KeyError as e:
        error_detail = {"detail": repr(e)}
        return Response(error_detail, status=status.HTTP_406_NOT_ACCEPTABLE)

    #return Response({"success": "Successfully parsered."})


    # check verification code
    try:
        vc = VerificationCode.objects.get(phone_number=phone_number)

        time_diff = datetime.now() - vc.created_time.replace(tzinfo=None)
        if int(time_diff.total_seconds()) > 600:
            vc.delete()

            error_detail = {"detail":
                            "Verification code has expired."}

            return Response(error_detail, status=status.HTTP_404_NOT_FOUND)

        if vc.verification_code != verification_code:
            error_detail = {"detail":
                            "Verification code is invalid."}

            return Response(error_detail, status=status.HTTP_406_NOT_ACCEPTABLE)

    except VerificationCode.DoesNotExist:
        error_detail = {"detail":
                        "Please wait a moment or re-enter verification code."}

        return Response(error_detail, status=status.HTTP_404_NOT_FOUND)

    # phone number check
    try:
        user = User.objects.get(username=phone_number)

    except User.DoesNotExist:
        error_detail = {"detail":
                        "The phone number is NOT registed."}
        return Response(error_detail, status=status.HTTP_404_NOT_FOUND)

    vc.delete()

    user.set_password(password)
    user.save()

    return Response({"success": "Successfully reset the password"})

@api_view(['PUT'])
@permission_classes((IsAuthenticated,))
def update_password_api(request):
    parser = JSONParser
    confirmed = 'no'
    data = request.data
    user = request.user

    old_password = data.get('old_password')
    new_password = data.get('new_password')

    if not old_password or not new_password:
        detail = ('Please provide password for user[%s]' % user.username)
        logger.error(detail)
        return Response({'detail': detail}, status=status.HTTP_406_NOT_ACCEPTABLE)

    auth = authenticate(username=user.username, password=old_password)
    if auth is not None:
        user.set_password(new_password)
        user.save()
        logger.info('User[%s]\'s password changed.')
        return Response({"success": "Successfully updated the password"})
    else:
        detail = 'The old password is not correct.'
        logger.error(detail)
        return Response({'detail': detail},status=status.HTTP_401_UNAUTHORIZED)



@api_view(['POST'])
@permission_classes((IsAuthenticated,))
def reset_payment_password_api(request):
    parser = JSONParser
    confirmed = 'no'
    data = request.data
    user = request.user
    logger.info(data)

    #return Response({"success": "Successfully parsered."})


    try:
        phone_number = user.username
    #password = request.GET.get('password')
        password = data.get('password')
        verification_code = data.get('verification_code')
        #confirmed = request.GET.get('confirmed')
    except KeyError as e:
        detail = {'detail': repr(e)}
        return Response(detail, status=status.HTTP_406_NOT_ACCEPTABLE)

    #return Response({"success": "Successfully parsered."})


    # check verification code
    try:
        vc = VerificationCode.objects.get(phone_number=phone_number)

        time_diff = datetime.now() - vc.created_time.replace(tzinfo=None)
        if int(time_diff.total_seconds()) > 600:
            vc.delete()

            detail = {'detail':
                            'Verification code has expired.'}

            return Response(detail, status=status.HTTP_404_NOT_FOUND)

        if vc.verification_code != verification_code:
            detail = {'detail':
                            'Verification code is invalid.'}

            return Response(detail, status=status.HTTP_406_NOT_ACCEPTABLE)

    except VerificationCode.DoesNotExist:
        detail = {'detail':
                        'Please wait a moment or re-enter verification code.'}

        return Response(detail, status=status.HTTP_404_NOT_FOUND)

    # phone number check
    try:
        up = UserProfile.objects.get(user=user)

    except UserProfile.DoesNotExist:
        detail = {'detail':
                        'Failed to get user profile'}
        return Response(detail, status=status.HTTP_404_NOT_FOUND)

    vc.delete()

    up.payment_password = password
    up.save()

    return Response({'success': 'Successfully reset the payment password'})

@api_view(['PUT'])
@permission_classes((IsAuthenticated,))
def update_payment_password_api(request):
    parser = JSONParser
    confirmed = 'no'
    data = request.data
    user = request.user

    old_password = data.get('old_password')
    new_password = data.get('new_password')

    if not old_password or not new_password:
        detail = ('Please provide password for user[%s]' % user.username)
        logger.error(detail)
        return Response({'detail': detail}, status=status.HTTP_406_NOT_ACCEPTABLE)

    try:
        up = UserProfile.objects.get(user=user)

    except UserProfile.DoesNotExist:
        detail = {'detail':
                        'Failed to get user profile'}
        return Response(detail, status=status.HTTP_404_NOT_FOUND)

    if old_password == up.payment_password:
        up.payment_password = new_password
        up.save()
        logger.info('User[%s]\'s payment password changed.')
        return Response({'success': 'Successfully updated the payment password'})
    else:
        detail = 'The old password is not correct.'
        logger.error(detail)
        return Response({'detail': detail},status=status.HTTP_401_UNAUTHORIZED)


