import tqdm
import json
import time
import heapq
import spotipy
import logging
import requests
from pymongo import MongoClient
from spotipy.oauth2 import SpotifyClientCredentials
from multiprocessing import Pool, Manager
from functools import partial

API_URL = "https://api.spotify.com/v1/"
N_RECOMMENDATIONS = 100  # max is 100
TIMEOUT_AFTER = 10  # request retries


class PrioritySet(object):
    def __init__(self):
        self.heap = []
        self.set = set()

    def add(self, d, pri):
        if not d in self.set:
            heapq.heappush(self.heap, (pri, d))
            self.set.add(d)

    def pop(self):
        pri, d = heapq.heappop(self.heap)
        self.set.remove(d)
        return pri, d


def scrape_recommendations(client_id, client_secret):
    manager = Manager()
    namespace = manager.Namespace()
    namespace.set = manager.dict()
    namespace.credentials_manager = SpotifyClientCredentials(client_id=client_id, client_secret=client_secret)
    sp = spotipy.Spotify(client_credentials_manager=namespace.credentials_manager)
    genres = sp.recommendation_genre_seeds()["genres"]
    worker = partial(scraping_worker, namespace)
    with Pool(processes=len(genres)) as pool:
        pool.map(worker, genres)


def scraping_worker(namespace, seed):
    logging.basicConfig(format='%(asctime)s %(message)s',
                        datefmt='%m/%d/%Y %H:%M:%S',
                        filename='scraping.log', level=logging.INFO)

    logging.info("started thread '{}'".format(seed))
    client = MongoClient("localhost", 27017)
    db = client.spotify
    recommendation_col = db.recommendations
    recommendation_col.create_index("for")
    artist_col = db.artists
    artist_col.create_index("id", unique=True)
    album_col = db.albums
    album_col.create_index("id", unique=True)
    meta_col = db.meta
    meta_col.create_index("id", unique=True)

    header = {"Authorization": "Bearer {}".format(namespace.credentials_manager.get_access_token())}
    result = request(header, "{}recommendations?seed_genres={}&limit=100".format(API_URL, seed), name=seed)

    queue = PrioritySet()

    for recommendation in result["tracks"]:
        for artist in recommendation["artists"]:
            if artist["id"] not in namespace.set:
                record = meta_col.find_one({"id": artist["id"]})
                priority = record["n_queried"] if record is not None else 0
                queue.add(artist["id"], priority)
            namespace.set[artist["id"]] = None

    while queue.heap[0][0] < 3:
        count, artist_id = queue.pop()

        result = request(header,
                         "{}recommendations?seed_artists={}&limit={}".format(API_URL, artist_id, N_RECOMMENDATIONS),
                         name=seed)

        meta_col.update({"id": artist_id}, {"id": artist_id, "n_queried": count + 1}, True)
        queue.add(artist_id, count + 1)

        for recommendation in result["tracks"]:
            for artist in recommendation["artists"]:
                artist_col.update({"id": artist["id"]}, {"id": artist["id"], "name": artist["name"]}, True)
                if artist["id"] not in namespace.set:
                    record = meta_col.find_one({"id": artist["id"]})
                    priority = record["n_queried"] if record is not None else 0
                    queue.add(artist["id"], priority)
                    namespace.set[artist["id"]] = None
            album_col.update({"id": recommendation["album"]["id"]},
                             {"id": recommendation["album"]["id"],
                              "name": recommendation["album"]["name"],
                              "artists": [x["id"] for x in recommendation["album"]["artists"]]}, True)
            recommendation_col.insert_one({
                "for": artist_id,
                "album": recommendation["album"]["id"],
                "artists": [x["id"] for x in recommendation["artists"]],
                "popularity": recommendation["popularity"]
            })


def request(header, url, name=""):
    for _ in range(TIMEOUT_AFTER):
        result = requests.get(url, headers=header)
        if result.ok:
            return result.json()
        logging.info("thread '{}': timeout of {}s".format(name, result.headers["Retry-After"]))
        try:
            time.sleep(int(result.headers["Retry-After"]))
        except KeyError:
            logging.warning("no retry-after header found")
    logging.warning("exiting thread '{}' after {} retries".format(name, TIMEOUT_AFTER))
    exit()


if __name__ == "__main__":
    with open("credentials.json", "r") as file:
        credentials = json.load(file)
    scrape_recommendations(client_id=credentials["client_id"], client_secret=credentials["client_secret"])
