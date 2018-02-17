# coding: utf-8
from __future__ import unicode_literals

import re, sys, os

from .common import InfoExtractor
import xml.etree.ElementTree as ET
from html.parser import HTMLParser


class CBCOlympicsIE(InfoExtractor):
    IE_NAME = 'olympics.cbc.ca'
    _VALID_URL = r'https?://(?:www\.)?olympics\.cbc\.ca/video/.*/(?P<id>[a-zA-Z0-9-]+)/?'
    _GEO_COUNTRIES = ['CA']
    _TESTS = [{
        # Replay with number in URL
        'url': 'https://olympics.cbc.ca/video/todays-events/hockey-feb-usa-can-women-preliminary-action-45294/',
        # 'md5': 'TODO: md5 sum of the first 10241 bytes of the video file (use --test)',
        'info_dict': {
            'id': 'hockey-feb-usa-can-women-preliminary-action-45294',
            'title': 'Hockey, Feb. 14: USA vs. CAN in women\'s preliminary action',
            'description': 'Watch the United States vs. Canada in women\'s preliminary round hockey action from the Kwandong Centre.',
            'ext': 'mp4',
        },
    }, {
        # Replay without number in URL
        'url': 'https://olympics.cbc.ca/video/todays-events/curling-feb-men-den-sui/',
        # 'md5': 'todo',
        'info_dict': {
            'id': 'curling-feb-men-den-sui',
            'title': 'Curling, Feb. 15: men\'s (DEN vs. SUI)',
            'description': 'Watch Denmark vs. Switzerland in men\'s curling Draw 3 action.',
            'ext': 'mp4',
        },
    }, {
        # Highlight URL
        'url': 'https://olympics.cbc.ca/video/highlights/eeli-tolvanen-four-point-night-leads-finland-win-over-germany/',
        # 'md5': 'todo',
        'info_dict': {
            'id': 'eeli-tolvanen-four-point-night-leads-finland-win-over-germany',
            'title': 'Eeli Tolvanen\'s 4 point night leads to Finland win over Germany',
            'description': 'Nashville Predators prospect Eeli Tolvanen had a goal and three assists, including the eventual game-winner, as Finland opened the Olympic tournament with a 5-2 win over Germany.',
            'ext': 'mp4',
        },
    }, {
        # VOD URL
        'url': 'https://olympics.cbc.ca/video/vod/hearts-hugs-and-kisses-for-valentine-day/',
        # 'md5': 'todo',
        'info_dict': {
            'id': 'hearts-hugs-and-kisses-for-valentine-day',
            'title': 'Hearts, hugs and kisses for Valentine\'s Day',
            'description': 'The competition is tense, but there\'s still lots of love at the Winter Olympics. Check out all the hugs, kisses, hearts and emotion on display in Korea.',
            'ext': 'mp4',
        },
    }]
    _DATA_URL_TEMPLATE = "https://olympics.cbc.ca/videodata/%s.xml"

    _USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36" + \
             "(KHTML, like Gecko) Chrome/63.0.3239.132 Safari/537.36"
    _FRAGMENT_PATTERN = "video=(\d+),format="
    _FRAGMENT_REGEX = re.compile(_FRAGMENT_PATTERN)
    _FRAGMENT_ARGS = "QualityLevels(3449984)/Fragments(video=%s," + \
                    "format=m3u8-aapl-v3,audiotrack=english)"
    _MANIFEST_ARGS = "QualityLevels(3449984)/Manifest(video," + \
                    "format=m3u8-aapl-v3,audiotrack=english,filter=hls)"

    def get_id(self, url, video_id):
        response = self._download_webpage(url, video_id, note=False)
        content_id = self._html_search_regex(r'<meta name="rc.idMedia" content="(.+?)"',
            response, u'content ID')
        return content_id

    def get_manifest_link(self, content_id, video_id):
        xml_link = CBCOlympicsIE._DATA_URL_TEMPLATE % (content_id)
        response = self._download_webpage(xml_link, video_id,
            headers={"User-Agent": CBCOlympicsIE._USER_AGENT}, note=False)
        tree = ET.fromstring(response.encode('utf-8'))
        elt = tree.find ("videoSources")
        for child in elt:
            if child.attrib["format"] == "HLS":
                return child.find("uri").text

    def fetch_file(self, filename_and_url, video_id, directory):
        if os.path.exists(filename_and_url[0]):
            return
        response = self._download_webpage(filename_and_url[1], video_id,
            headers={"User-Agent": CBCOlympicsIE._USER_AGENT}, note=False)
        with open(os.path.join(directory, filename_and_url[0] + ".part"), "wb") as f:
            for chunk in response:
                f.write(chunk.encode('utf-8'))

    def _real_extract(self, url):
        folder = "_ytdl-temp"
        video_id = self._match_id(url)
        webpage = self._download_webpage(url, video_id)

        xml_id = self.get_id(url, video_id)
        manifest_link = self.get_manifest_link(xml_id, video_id)

        ism_link = manifest_link.split(".ism/", 1)[0].strip() + ".ism/"
        # highlights need lower case manifest, no qualitylevels argument
        manifest_text = self._download_webpage(ism_link + CBCOlympicsIE._MANIFEST_ARGS,
            video_id, headers={"User-Agent": CBCOlympicsIE._USER_AGENT}, note=False)
        content_numbers = re.findall(CBCOlympicsIE._FRAGMENT_REGEX, manifest_text)

        urls = []
        for n in content_numbers:
            urls.append((ism_link + (CBCOlympicsIE._FRAGMENT_ARGS % (n))))

        if not os.path.exists(folder):
            os.makedirs(folder)

        with open(os.path.join("_ytdl-temp", "_files.txt"), 'w') as f:
            f.write("\n".join(["file '{}.part'".format(n)
                               for n in content_numbers]))

        number_parts = len(urls) # or content_numbers

        filenames_and_urls = list(zip(content_numbers, urls))
        for idx, value in enumerate(filenames_and_urls):
            sys.stdout.write("Fetching part %i / %i... " % (idx+1, number_parts))
            sys.stdout.flush()
            sys.stdout.write("\r")
            self.fetch_file(value, video_id, folder)

        filelist = os.path.join("_download", "_files.txt")
        filename = video_id + ".mp4"
        subprocess.call(["ffmpeg", "-f", "concat", "-safe", "0", "-i",
                         filelist, "-c:v", "copy", "-c:a", "copy",
                         "-bsf:a", "aac_adtstoasc", filename])

        video_url = urls[0]

        return {
            '_type': 'video',
            'id': xml_id,
            'url': video_url,
            'title': self._og_search_title(webpage, fatal=False).split('|', 1)[0].strip(),
            'description': self._og_search_description(webpage),
            'ext': 'mp4', # check
        }
