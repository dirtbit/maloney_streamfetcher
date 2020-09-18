#!/usr/bin/python
#-------------------------------------------------------------------------------
# Import modules
#
import pycurl
import os, io
import shutil
import argparse
import unicodedata

import certifi
import json
import urllib2

#-------------------------------------------------------------------------------
# Class Maloney Download
#
class maloney_download:
  '''
  Downloads Maloney Episodes
  '''
  verbose = False

  def __init__(self, verbose=False):
    # Change to script location
    path,file=os.path.split(os.path.realpath(__file__))
    os.chdir(path)
    self.path = path
    self.verbose = verbose

  def fetch_latest(self, outdir = None, uid = None):
    #old URL: srf_maloney_url = "https://www.srf.ch/sendungen/maloney/"
    srf_maloney_url = "https://www.srf.ch/audio/maloney"
    self.process_maloney_episodes(srf_maloney_url, outdir=outdir, uid=uid)

  def fetch_all(self, outdir = None, uid = None):
    srf_maloney_url    = "https://www.srf.ch/sendungen/maloney/layout/set/ajax/Sendungen/maloney/sendungen/(offset)/"

    for i in range(0,510,10): # each page shows 10 items per page, iterate through pages
      url = srf_maloney_url + str(i)
      if (self.process_maloney_episodes(url, i, outdir=outdir, uid=uid) > 0) and uid: # if uid is set and download worked -> exit
        return

  def process_maloney_episodes(self, url, offset = 0, outdir=None, uid=None):
    # Constants
    path_to_ffmpeg   = self.path
    ffmpeg = path_to_ffmpeg + "/ffmpeg"
    
    path_to_rtmpdump = self.path 
    rtmpdump = path_to_rtmpdump + "/rtmpdump"
        
    path_to_mid3v2   = self.path
    mid3v2   = "python " + path_to_mid3v2 + "/mid3v2.py"

    temp_directory   = "./temp"
    #old URL: json_url         = "https://il.srgssr.ch/integrationlayer/2.0/srf/mediaComposition/audio/"
    json_url         = "https://il.srgssr.ch/integrationlayer/2.0/mediaComposition/byUrn/urn:srf:audio:"

    # Get user constants
    if outdir == None:
      out_dir = "."
    elif os.path.isdir(outdir):
      out_dir = outdir
    else:
      self.log("Given output directory doesn't exist")
      return None

    # Get page content and id's
    if uid == None:
      id = [0,1,2,3,4,5,6,7,8,9]
      self.log("No ID given, will download all available episodes from the mainpage")
      # Get page info
      page = self.curl_page(url)
      uids = self.parse_html(page)
    else:
      uids = [uid]

    # Read JSON Data
    json_data = self.get_jsondata(json_url, uids)

    # Download Files
    self.log("Get Episodes")
    # Create tmp directory
    if not os.path.exists(temp_directory):
      os.makedirs(temp_directory)
    cnt = 0
    idx = []
    for episode in json_data:
      if os.path.isfile(out_dir + "/" + episode["mp3_name"]):
        self.log("  Episode \"{} - {}\" already exists in the output folder {}".format(episode["year"], episode["title"], out_dir + "/" + episode["mp3_name"]))
        self.log("    Skipping Episode ...")
      else:
        idx.append(cnt)
        
        # two possibilities for raw data: 
        #    RTMP: FLV -> MP3 -> add ID3
        #    HTTPS: MP -> add ID3
        
        if episode['httpsurl'] == '':
          # Download with RTMP
          self.log("  RTMP download...")
          command = rtmpdump + " -r " + episode["rtmpurl"] + "  -o \"" + temp_directory + "/stream_dump.flv\""
          self.system_command(command)

          # Convert to MP3
          self.log("  FFMPEG conversion flv to MP3...")
          command = ffmpeg + " -y -loglevel panic -stats -i " + temp_directory + "/stream_dump.flv -vn -c:a copy \"" + out_dir + "/" + episode["mp3_name"] + "\""
          self.system_command(command)
          
        else:
          # Download via HTTPS
          self.log("  HTTPS download...")
          self.log(episode['httpsurl'])
          mp3file = urllib2.urlopen(episode['httpsurl'])
          with open(out_dir + "/" + episode["mp3_name"],'wb') as output:
            output.write(mp3file.read())
          

        # Add ID3 Tag
        self.log("  Adding ID3 Tags...")
        command = ("{} -t \"{} - {}\" \"{}\"").format(mid3v2, episode["date"], episode["title"], out_dir + "/" + episode["mp3_name"])
        self.system_command(command)
        command = ("{} -A \"{}\" \"{}\"").format(mid3v2, "Maloney Philip", out_dir + "/" + episode["mp3_name"])
        self.system_command(command)
        command = ("{} -a \"{}\" \"{}\"").format(mid3v2, "Graf Roger", out_dir + "/" + episode["mp3_name"])
        self.system_command(command)
        command = ("{} -g \"{}\" \"{}\"").format(mid3v2, "Book", out_dir + "/" + episode["mp3_name"])
        self.system_command(command)
        command = ("{} -y \"{}\" \"{}\"").format(mid3v2, episode["year"], out_dir + "/" + episode["mp3_name"])
        self.system_command(command)
        command = ("{} -c \"{}\" \"{}\"").format(mid3v2, episode["lead"], out_dir + "/" + episode["mp3_name"])
        self.system_command(command)
      cnt = cnt + 1

    # Deleting tmp directory
    shutil.rmtree(temp_directory)

    print("------------------------------------------------------")
    print(" Finished downloading {} Episodes from page with offset {}".format(len(idx), offset))
    for id in idx:
      print("  * {}".format(out_dir + "/" + json_data[id]["mp3_name"]))
    print("------------------------------------------------------")
    return cnt

  def curl_page(self, url):
    buffer = io.BytesIO()
    c = pycurl.Curl()
    c.setopt(c.WRITEFUNCTION, buffer.write)
    c.setopt(c.URL, url)
    c.setopt(c.WRITEDATA, buffer)
    c.setopt(pycurl.CAINFO, certifi.where())
    c.perform()
    c.close()
    return buffer.getvalue().decode("utf-8")

  def parse_html(self, page):
    lines = unicodedata.normalize('NFKD', page).encode('ascii','ignore')
    lines = str(lines).split("\n")

    uids = []

    for line in lines:
      if '/popupaudioplayer' in line:
        pos = line.find("?id=") + 4
        uids.append(line[pos:-2])

    if (len(uids) > 0):
      self.log("Found ID's")
      for i in range(len(uids)):
        self.log("  * ID {} = {} ".format(i, uids[i]))
    return uids

  def get_jsondata(self, jsonurl, uids):
    json_data = []
    for uid in uids:
      url = jsonurl + uid + ".json"
      page = self.curl_page(url)
      (mp3_name, title, lead, rtmpurl, httpsurl, year, date) = self.parse_json(page)
      json_data.append({"mp3_name": mp3_name, "title": title, "lead": lead, "rtmpurl":rtmpurl, "httpsurl":httpsurl, "year":year, "date":date})
    return json_data
      
  def parse_json(self, json_string):
    json_string = unicodedata.normalize('NFKD', json_string).encode('ascii','ignore') # we're not interested in any non-unicode data
    jsonobj = json.loads(json_string)
    
    title = jsonobj['chapterList'][0]['title']
    lead = jsonobj['chapterList'][0]['lead']
    publishedDate = jsonobj['episode']['publishedDate']
    
    for x in range(0, len(jsonobj['chapterList'][0]['resourceList'])):
        if 'RTMP' in jsonobj['chapterList'][0]['resourceList'][x]['protocol']:
          rtmpurl = jsonobj['chapterList'][0]['resourceList'][x]['url']
        if 'HTTPS' in jsonobj['chapterList'][0]['resourceList'][x]['protocol']:
          httpsurl = jsonobj['chapterList'][0]['resourceList'][x]['url']
    
    year = jsonobj['chapterList'][0]['date'][:4]
    date = jsonobj['chapterList'][0]['date'][:10]
    mp3_name = "{} - Maloney Philip - {}.mp3".format(date, title)
    
    self.log("    MP3 Filename: {}".format(mp3_name))
    self.log("      * Title       :{} Date:{}".format(title, publishedDate, year))
    self.log("      * RTMP Url    :{}".format(rtmpurl))
    self.log("      * HTTPS Url   :{}".format(httpsurl))
    self.log("      * Lead        :{}".format(lead))    
    
    return (mp3_name, title, lead, rtmpurl, httpsurl, year, date)
      
  def system_command(self, command):
    self.log(command)
    os.system(command)

  def log(self, message):
    if self.verbose:
      print(message)

#-------------------------------------------------------------------------------
# Execute
#
if __name__ == "__main__":

  parser = argparse.ArgumentParser(description = 'Options for maloney_streamfetcher script')
  parser.add_argument('-a', '--all', action='store_false', dest='latest', help='Download all 500 last Maloney episodes. Does not work for the newest one or two, use -l instead.')
  parser.add_argument('-l', '--latest', action='store_true', dest="latest", help='Download the last 10 Maloney episodes, works also for the newest ones ;-).')
  parser.add_argument('-o', '--outdir', dest='outdir', help='Specify directory to store episodes to.')
  parser.add_argument('-u', '--uid', dest='uid', help='Download a single episode by providing SRF stream UID.')
  parser.add_argument('-v', '--verbose', action='store_true', dest='verbose', help='Enable verbose.')
  args = parser.parse_args()

  latest = args.latest

  maloney_downloader = maloney_download(verbose=args.verbose)

  if latest:
    maloney_downloader.fetch_latest(outdir = args.outdir, uid=args.uid)
  else: # default setting
    maloney_downloader.fetch_all(outdir = args.outdir, uid=args.uid)