#!/usr/bin/python3

import glob, time, sys, getopt, argparse, os, socket, smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

class Namespace:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

class Conf:
    def_decimals   = 4
    def_timestamp  = False
    def_resolution = 12
    family         = 28
    retry_sleep    = 0.2
    device_file    = 'w1_slave'
    device_dir     = '/sys/bus/w1/devices'
    sensors_dir    = glob.glob(f'{device_dir}/{family}*')
    resolution     = {
            9 : 0.5,
            10: 0.25,
            11: 0.125,
            12: 0.0625
            }

def read_temp(filename):
    for i in range(3):
        try:
            f = open(filename, 'r')
            lines = f.readlines()
            f.close()
        except Exception as e:
            print(e, file=sys.stderr)
            continue

        if len(lines) !=2 or lines[0].strip()[-3:] != 'YES':
            time.sleep(Conf.retry_sleep)
        else:
            temp_pos = lines[1].find('t=')
            if temp_pos != -1:
                temp_string = lines[1][temp_pos+2:]
                temp_c = float(temp_string) / 1000.0
                temp_f = temp_c * 9.0 / 5.0 + 32.0
                return temp_c, temp_f

    raise Exception(f'Error reading temp from file: {filename}')

def read(args):
    for sensor in args.sensor_id:
        try:
            temp = read_temp(f'{Conf.device_dir}/{Conf.family}-{sensor}/{Conf.device_file}')
            timestamp = ''

            if args.timestamp:
                timestamp = int(round(time.time() * 1000))

            temp_c = '{:.{}f}'.format(temp[0], args.decimals)
            temp_f = '{:.{}f}'.format(temp[1], args.decimals)

            line_proto = f'sensors,sensor_id={sensor} temp_c={temp_c},temp_f={temp_f} {timestamp}'.strip()
            print(line_proto)
        except Exception as e:
            print(e, file=sys.stderr)
            continue

def init(args):
    for sensor in args.sensor_id:
        try:
            f = open(f'{Conf.device_dir}/{Conf.family}-{sensor}/{Conf.device_file}', 'w')
            f.write(str(args.resolution))
            f.close()
            print(f'Sensor {sensor} resolution set to {args.resolution} which is an increment of {Conf.resolution[args.resolution]}*C')
        except Exception as e:
            print(e, file=sys.stderr)
            continue


def send(args):

    addr = []

    for iface in socket.if_nameindex():
        iface = iface[1]
        split = os.popen(f'ip addr show {iface}').read().split("inet ")#[1].split("/")[0]
        if len(split) < 2:
            continue
        split = split[1].split('/')
        if len(split) < 2:
            continue
        ipv4 = split[0]
        addr.append([iface, ipv4])

    message = f"""\
Subject: Templogger connected to the internet
To: {args.to}
From: {args.from_mail}

{addr}"""
    try:
        server = smtplib.SMTP_SSL(args.server, args.port)
        server.login(args.username, args.password)
        server.sendmail(args.from_mail, args.to, message)
        print('Sent')
    except smtplib.SMTPServerDisconnected:
        print('Failed to connect to the server. Wrong user/password?')
    except smtplib.SMTPException as e:
        print('SMTP error occurred: ' + str(e))




if __name__ == '__main__':

    try:
        sensors_lst = []
        for dir in Conf.sensors_dir:
            sensors_lst.append(dir[-12:])

        sensors_str = ' '.join(sensors_lst)

        parser        = argparse.ArgumentParser(description='Read and configure DS18B20 sensors', epilog=f'Currently available sensors: {sensors_str}')
        parser.add_argument

        parser_action  = parser.add_subparsers(help='Choose action')
        parser_read    = parser_action.add_parser('read',    help='Read values from the sensors')
        parser_init    = parser_action.add_parser('init',    help='Configure the sensor\'s resolution')
        parser_send    = parser_action.add_parser('send', help='Send the host\'s IP address via email')

        parser_init.epilog = f'Currently attached sensors are: {sensors_str}'
        parser_init.set_defaults(func=init)
        parser_init.add_argument('-s',
                dest='sensor_id',
                type=str,
                nargs='+',
                default=sensors_lst,
                help='Select sensor. Omit argument to select all available sensors. To select a specific senseor enter it\'s 12 digit id')
        parser_init.add_argument('-r',
                dest='resolution',
                type=int,
                choices=range(9,13),
                default=Conf.def_resolution,
                help=f'Set the resolution of the selected sensors. 9={Conf.resolution[9]}*C 10={Conf.resolution[10]}*C 11={Conf.resolution[11]}*C 12={Conf.resolution[12]}*C')

        parser_read.epilog = f'Currently attached sensors are: {sensors_str}'
        parser_read.set_defaults(func=read)
        parser_read.add_argument('-s',
                dest='sensor_id',
                type=str,
                nargs='+',
                default=sensors_lst,
                help='Select sensor. Omit argument to select all available sensors. To select a specific senseor enter it\'s 12 digit id')
        parser_read.add_argument('-d', 
                dest='decimals',
                type=int, 
                choices=range(0,5),
                default=Conf.def_decimals,
                help='Set how many decimal points in the output of the command')
        parser_read.add_argument('-t', 
                dest='timestamp',
                action='store_true',
                default=Conf.def_timestamp,
                help='Output the timestamp')

        parser_send.set_defaults(func=send)
        parser_send.add_argument('-s',
                dest='server',
                type=str,
                required=True,
                help='SMTP server')
        parser_send.add_argument('-o',
                dest='port',
                type=str,
                required=True,
                help='SMTP port')
        parser_send.add_argument('-u',
                dest='username',
                type=str,
                required=True,
                help='SMTP login username')
        parser_send.add_argument('-p',
                dest='password',
                type=str,
                required=True,
                help='SMTP login pass')
        parser_send.add_argument('-f',
                dest='from_mail',
                type=str,
                required=True,
                help='Sender email address')
        parser_send.add_argument('-t',
                dest='to',
                type=str,
                required=True,
                help='Recipient email address')

        args = parser.parse_args()
        if hasattr(args, 'func'):
            try:
                args.func(args)
            except Exception as e:
                if args.func != read:
                    print(e)
                sys.exit(2)
        else:
            read(Namespace(decimals=Conf.def_decimals, timestamp=Conf.def_timestamp, sensor_id=sensors_lst))

    except Exception as e:
        print(e, file=sys.stderr)
        pass

