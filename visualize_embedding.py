import json
import tqdm
import requests
import spotipy
import numpy as np
from gensim.models import KeyedVectors
from sklearn import decomposition
from sklearn import manifold
from spotipy.oauth2 import SpotifyClientCredentials
from mpl_toolkits.mplot3d import Axes3D
import matplotlib.pyplot as plt

N_GENRES = 2
N_PER_GENRE = 20

embedding = KeyedVectors.load_word2vec_format("spotify2vec.txt")

# print(embedding.most_similar(positive=["Gojira"], topn=100))

pca = decomposition.PCA(n_components=3)
pca.fit(embedding.vectors)
# tsne = manifold.TSNE(n_components=3)
# reduced = tsne.fit_transform(embedding.vectors)

with open("credentials.json", "r") as file:
    credentials = json.load(file)

credentials_manager = SpotifyClientCredentials(client_id=credentials["client_id"],
                                               client_secret=credentials["client_secret"])
sp = spotipy.Spotify(client_credentials_manager=credentials_manager)
header = {"Authorization": "Bearer {}".format(credentials_manager.get_access_token())}
url = f"https://api.spotify.com/v1/recommendations?seed_genres={{}}&limit={N_PER_GENRE}"

# genres = np.random.choice(sp.recommendation_genre_seeds()["genres"], N_GENRES).tolist()
# genres = ["alternative", "classical", "edm", "metal", "pop"]
genres = ["alternative", "pop"]
artists = []
for genre in tqdm.tqdm(genres):
    recommendations = requests.get(url.format(genre), headers=header).json()
    for recommendation in recommendations["tracks"]:
        for artist in recommendation["artists"]:
            name = artist["name"].replace(" ", "_")
            if name in embedding.vocab:
                artists.append({
                    "name": artist["name"],
                    "vector": pca.transform([embedding[name]])[0],
                    "genre": genre
                    # "vector": reduced[embedding.vocab[name].index]
                })
                continue

cm = plt.get_cmap('gist_rainbow')
fig = plt.figure()
ax = fig.add_subplot(111, projection='3d')
X = [artist["vector"][0] for artist in artists]
Y = [artist["vector"][1] for artist in artists]
Z = [artist["vector"][2] for artist in artists]
C = [cm(genres.index(artist["genre"]) / len(genres)) for artist in artists]
# sc = ax.scatter(X, Y, Z, c=C, s=25)  #, alpha=0.4)
sc = ax.scatter(X, Y, Z, c=C, s=0)  #, alpha=0.4)
plt.draw()
# colors = sc.get_facecolors()
for x, y, z, artist in zip(X, Y, Z, artists):
    ax.text(x, y, z, artist["name"], color=cm(genres.index(artist["genre"]) / len(genres)), fontsize=8)
plt.show()
