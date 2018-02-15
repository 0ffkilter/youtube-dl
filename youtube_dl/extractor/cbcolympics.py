# coding: utf-8
from __future__ import unicode_literals

from .common import InfoExtractor
import os, sys, requests, re, subprocess, shutil
import xml.etree.ElementTree as ET
from multiprocessing import Pool
from tqdm import tqdm
from html.parser import HTMLParser



class CBCOlympicsIE(InfoExtractor):
    _USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36" + \
             "(KHTML, like Gecko) Chrome/63.0.3239.132 Safari/537.36"
    _FRAGMENT_PATTERN = "video=(\d+),format="
    _FRAGMENT_REGEX = re.compile(_FRAGMENT_PATTERN)
    _FRAGMENT_ARGS = "QualityLevels(3449984)/Fragments(video=%s," + \
                    "format=m3u8-aapl-v3,audiotrack=english)"
    _MANIFEST_ARGS = "QualityLevels(3449984)/Manifest(video," + \
                    "format=m3u8-aapl-v3,audiotrack=english,filter=hls)"
    _VALID_URL = r'https?://(?:www\.)?olympics\.cbc\.ca/video/.*/(?P<id>[0-9]+)'
    _TEST = {
        'url': 'https://yourextractor.com/watch/42',
        'md5': 'TODO: md5 sum of the first 10241 bytes of the video file (use --test)',
        'info_dict': {
            'id': '42',
            'ext': 'mp4',
            'title': 'Video title goes here',
            'thumbnail': r're:^https?://.*\.jpg$',
            # TODO more properties, either as:
            # * A value
            # * MD5 checksum; start the string with md5:
            # * A regular expression; start the string with re:
            # * Any Python type (for example int or float)
        }
    }

    class CBCHTMLParser(HTMLParser):

        def handle_starttag(self, tag, attrs):
            if tag == "meta":
                if attrs[0][1] == "rc.idMedia":
                    self.content_id = attrs[1][1]

    def get_id(self, url):
        parser = self.CBCHTMLParser()
        response = requests.get(url,
                                headers={"User-Agent": CBCOlympicsIE.USER_AGENT})
        parser.feed(response.text)
        return parser.content_id

    def get_ism_link(self, content_id):
        xml_link = CBCOlympicsIE._XML_FORMAT % (content_id)
        response = requests.get(xml_link,
                                headers={"User-Agent": CBCOlympicsIE.USER_AGENT})
        tree = ET.fromstring(response.text)
        elt = tree.find("videoSources")
        for child in elt:
            if child.attrib["format"] == "HLS":
                return child.find("uri").text

    def fetch_file(self, url):
        if os.path.exists(url[0]):
            return
        response = requests.get(url[1],
                                headers={"User-Agent": CBCOlympicsIE.USER_AGENT},
                                stream=True)
        with open(url[0], "wb") as f:
            for chunk in response:
                f.write(chunk)

    def _real_extract(self, url):
        video_id = self._match_id(url)
        webpage = self._download_webpage(url, video_id)

        os.makedirs("_download")
        cdn_link = self.get_ism_link(self.get_id(url))

        manifest_link = cdn_link[:cdn_link.find(".ism/") + 5]
        response = requests.get(manifest_link + CBCOlympicsIE._MANIFEST_ARGS,
                                headers={"User-Agent":
                                         CBCOlympicsIE._USER_AGENT})
        manifest_text = response.text
        content_numbers = re.findall(CBCOlympicsIE._FRAGMENT_REGEX,
                                     manifest_text)

        with open(os.path.join("_download", "_files.txt"), 'w') as f:
            f.write("\n".join(["file '{}.part'".format(n)
                               for n in content_numbers]))

        urls = []
        for n in content_numbers:
            out_path = os.path.join("_download", "%s.part" % (n))
            urls.append((out_path, manifest_link +
                         (CBCOlympicsIE._FRAGMENT_ARGS % (n))))

        number_parts = len(content_numbers)

        for idx, number in content_numbers:
            print("fetching part %i / %i" % (idx, number_parts))
            self.fetch_file(number)

        filelist = os.path.join("_download", "_files.txt")
        filename = video_id + ".mp4"
        subprocess.call(["ffmpeg", "-f", "concat", "-safe", "0", "-i",
                         filelist, "-c:v", "copy", "-c:a", "copy",
                         "-bsf:a", "aac_adtstoasc", filename])

        return {
            'id': video_id,
            'title': url[url.rfind("/") + 1:],
            'description': self._og_search_description(webpage),
            # TODO more properties (see youtube_dl/extractor/common.py)
        }
