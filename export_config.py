import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'parkhero.settings')

import string
import rsa

from xml.etree.ElementTree import ElementTree
from xml.etree.ElementTree import Element
from xml.etree.ElementTree import SubElement
from xml.etree.ElementTree import dump
from xml.etree.ElementTree import Comment
from xml.etree.ElementTree import tostring

from subprocess import call

import django
django.setup()

from parking.models import ParkingLot, ParkingSpace


def populate():
    return

def create_xml(name, id, key):
    ## Writing the content to xml document
    book = ElementTree()

    configuration = Element('configuration')
    book._setroot(configuration)

    startup = Element('startup')
    SubElement(startup,'supportedRuntime',{'version' :'v4.0', 'sku': '.NETFramework,Version=v4.0'})

    configuration.append(startup)

    appSettings = Element('appSettings')
    configuration.append(appSettings)

    SubElement(appSettings, 'add', {'key': 'autostart','value': '0'})
    SubElement(appSettings, 'add', {'key': 'parkname','value': name})
    SubElement(appSettings, 'add', {'key': 'parkid','value': id})
    SubElement(appSettings, 'add', {'key': 'parkkey','value': key})
    SubElement(appSettings, 'add', {'key': 'parkedition','value': '0'})
    SubElement(appSettings, 'add', {'key': 'dbserver','value': 'db server ip'})
    SubElement(appSettings, 'add', {'key': 'database','value': 'db name'})
    SubElement(appSettings, 'add', {'key': 'username','value': 'sa'})
    SubElement(appSettings, 'add', {'key': 'password','value': '26997211'})
    SubElement(appSettings, 'add', {'key': 'cloudip','value': '120.25.60.20'})
    SubElement(appSettings, 'add', {'key': 'port','value': '2003'})
    SubElement(appSettings, 'add', {'key': 'Intervaltime','value': '10'})

    #print(tostring(indent(configuration)).decode('utf-8'))

    xml_declaration = '<?xml version="1.0" encoding="UTF-8"?>\n'
    indented = indent(configuration)
    #print(tostring(configuration))
    #print(name)
    xml_body = tostring(indent(configuration)).decode('utf-8')
    xml = xml_declaration + xml_body

    xml_file = '客户端上传工具.exe.Config'# + name + '.xml'
    #print(xml)
    book.write(xml_file, 'utf-8')

    with open(xml_file, 'r') as original:
        data = original.read()
        original.close()

    with open(xml_file, 'w') as modified:
        modified.write(xml_declaration + data)
        modified.close()
    #with open('客户端上传工具.exe.Config','w') as xml_file:
    #    xml_file.write(xml)
    #    xml_file.close()

## Get pretty look
def indent(elem, level=0):
    i = "\n" + level*"  "
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + "  "
        for e in elem:
            indent(e, level+1)
        if not e.tail or not e.tail.strip():
            e.tail = i
    if level and (not elem.tail or not elem.tail.strip()):
        elem.tail = i
    return elem

def generate_7z(name):
    file_name = '客户端上传工具-' + name
    call(['tar', '-xvf', 'upload_tool.tar'])
    call(['mv', '客户端上传工具', file_name])
    call(['mv', '客户端上传工具.exe.Config', './' + file_name])
    call(['7z', 'a', file_name + '.7z', file_name])
    call(['rm', '-fr', file_name])
    #call(['tar', '-cvf', '客户端上传工具-name.tar', './客户端上传工具'])
    #call(['zip', '-r', 'uptool.zip', '客户端上传工具'])

# Start execution here!
if __name__ == '__main__':
    print ("Starting client upload configuration generation script...")
    #populate()
    lots = ParkingLot.objects.all()
    for lot in lots:
        print('Creating xml for [%s]',lot.name)
        name = lot.name

        # remove '\n', key header, key footer
        key = lot.private_key.strip()
        key = key.replace('\n','')
        key = key.replace('-----BEGIN PRIVATE KEY-----','')
        key = key.replace('-----END PRIVATE KEY-----','')
        #print(key)
        identifier = str(lot.identifier)
        create_xml(name,identifier,key)
        generate_7z(name)



