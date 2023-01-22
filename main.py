import json
import logging
import seqlog
import os                                                  # import os module
import glob                                                # import glob module
import time                                                # import time module
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS
from secrets import Db
from secrets import Log

db = Db()
log= Log()

os.system('modprobe w1-gpio')                              # load one wire comm$
os.system('modprobe w1-therm')                                                 
base_dir = '/sys/bus/w1/devices/'                          # point to the addre$
device_folder = glob.glob(base_dir + '28*')[0]             # find device with a$
device_file = device_folder + '/w1_slave'                  # store the details
bucket = "pi-temp"
client = InfluxDBClient(url=db.url, token=db.token)

write_api = client.write_api(write_options=SYNCHRONOUS)
first_read = True
itr = 0
sensor_id = None
invalid_sensor="ff"

seqlog.log_to_seq(
server_url=log.url,
   api_key=log.token,
   level=logging.DEBUG,
   batch_size=10,
   auto_flush_timeout=10,  # seconds
   override_root_logger=True,
   json_encoder_class=json.encoder.JSONEncoder
)

def read_temp_raw():
   f = open(device_file, 'r')
   lines = f.readlines()                                   # read the device de$
   f.close()
   return lines

def read_temp():
   global sensor_id
   logging.info("read temperature lines")
   lines = read_temp_raw()
   while len(lines)!=2:
      logging.info("not 2 lines, re-read in 0.2 seconds", raw=lines)
      time.sleep(0.2)
      lines = read_temp_raw()

   while lines[0].strip()[-3:] != 'YES':                   # ignore first line
      logging.info("first line not YES, re-read in 0.2 seconds", raw=lines)
      time.sleep(0.2)
      lines = read_temp_raw()

   logging.debug("{lines}",lines=lines)
   equals_pos = lines[1].find('t=')                        # find temperature i$
   if equals_pos != -1:
      logging.info("found temperature")
      s_id = lines[1][0:26]
      crc_pos = lines[1].find('crc')
      crc_value = lines[1][crc_pos + 4: crc_pos + 6]

      if crc_value == invalid_sensor:
        return None, None

      if sensor_id is None:
        logging.info("set sensor id to {sensor}", sensor = s_id)
        sensor_id = s_id

      if sensor_id == s_id:

        temp_string = lines[1][equals_pos+2:]
        temp_c = float(temp_string) / 1000.0                 # convert to Celsi$
        temp_f = temp_c * 9.0 / 5.0 + 32.0                   # convert to Fahre$
        logging.info("the current temperature is {temp} C", temp=temp_c)
        return temp_c, temp_f

      else:
        logging.info("resetting sensor id {sensor} to None", sensor=sensor_id)
        sensor_id = None
   
   return None, None

while True:
   logging.debug("start loop {iteration}", iteration=itr)
   try:
      centigrade, farenheit = read_temp()
      logging.info("read temperature")
      if itr and centigrade is not None:
        logging.info("create point measurement")
        p = Point("my_measurement").tag("location", "water tank").field("temperature", centigrade)        
        logging.info("writing to influx db")
        write_api.write(bucket=bucket, org="rcl", record=p)                    $
        logging.info("writen to influx db")
      time.sleep(300)
      logging.info("setting first read to false")
      first_read = False
   except Exception as e:
      logging.error('Error at %s', 'division', exc_info=e)
      logging.warning("resetting iteration to zero")
      itr = 0

   logging.debug("complete loop {iteration}", iteration=itr)
   itr= itr + 1
