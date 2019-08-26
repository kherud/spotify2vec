import tqdm
import pickle
import numpy as np

""" Write .npy glove weights to a text file """

PRECISION = 6

print("load vocab")
with open("vocabulary.pkl", "rb") as file:
    vocabulary = {int(x["id"]): x["name"] for x in pickle.load(file).values()}

print("load embeddings")
embedding = np.load("glove-weights.npy")

print(embedding.shape)

print("write txt")
with open("spotify2vec.txt", "w") as file:
    file.write(f"{len(vocabulary)} {embedding.shape[1]}\n")
    for index, name in tqdm.tqdm(vocabulary.items()):
        file.write(f"{name.replace(' ', '_')} {' '.join(format(x, f'.{PRECISION}f') for x in embedding[index])}\n")