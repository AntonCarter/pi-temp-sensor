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
sample_interval = 300

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
   logging.debug("read temperature lines")
   lines = read_temp_raw()
   while len(lines)!=2:
      logging.debug("not 2 lines, re-read in 0.2 seconds", raw=lines)
      time.sleep(0.2)
      lines = read_temp_raw()

   while lines[0].strip()[-3:] != 'YES':                   # ignore first line
      logging.info("first line not YES, re-read in 0.2 seconds", raw=lines)
      time.sleep(0.2)
      lines = read_temp_raw()

   logging.debug("{lines}",lines=lines)
   equals_pos = lines[1].find('t=')                        # find temperature i$
   if equals_pos != -1:
      logging.debug("found temperature")
      temp_string = lines[1][equals_pos+2:]
      logging.debug("convert the temp string {tempstring} to a number ", tempstring=temp_string)
      temp_c = float(temp_string) / 1000.0                 # convert to Celsi$
      temp_f = temp_c * 9.0 / 5.0 + 32.0                   # convert to Fahre$
      logging.info("the current temperature is {temp} C", temp=temp_c)
      return temp_c, temp_f

   return None, None

while True:
   try:
      centigrade, farenheit = read_temp()

      if centigrade is not None:
        p = Point("my_measurement").tag("location", "water tank").field("temperature", centigrade)        
        write_api.write(bucket=bucket, org="rcl", record=p)
        logging.info("writen to influx db")
      time.sleep(sample_interval)

   except Exception as e:
      logging.error('error writing to database', exc_info=e)
