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
from requests.adapters import HTTPAdapter


API_URL = "https://api.spotify.com/v1/"
N_RECOMMENDATIONS = 10  # max is 100
TIMEOUT_AFTER = 10  # request retries


def scrape_recommendations(client_id, client_secret):
    manager = Manager()
    namespace = manager.Namespace()
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

    s = requests.Session()
    s.mount('https://api.spotify.com', HTTPAdapter(max_retries=10000))
    header = {"Authorization": "Bearer {}".format(namespace.credentials_manager.get_access_token())}
    result = request(header, "{}recommendations?seed_genres={}&limit=100".format(API_URL, seed), name=seed)

    queue = []

    for recommendation in result["tracks"]:
        for artist in recommendation["artists"]:
            queue.insert(0, artist["id"])

    while True:
        artist_id = queue.pop()

        result = request(header,
                         "{}recommendations?seed_artists={}&limit={}".format(API_URL, artist_id, N_RECOMMENDATIONS),
                         name=seed)

        meta_col.update_one({"id": artist_id}, {"$inc": {"n_queried": 1}}, True)

        for recommendation in result["tracks"]:
            for artist in recommendation["artists"]:
                artist_col.update_one({"id": artist["id"]}, {"$set": {"name": artist["name"]}}, True)
                queue.insert(0, artist["id"])
            album_col.update_one({"id": recommendation["album"]["id"]}, {"$set":
                             {"name": recommendation["album"]["name"],
                              "artists": [x["id"] for x in recommendation["album"]["artists"]]}}, True)
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
