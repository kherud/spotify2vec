import tqdm
import pickle
import matplotlib.pyplot as plt
from pymongo import MongoClient


def create_matrix():
    cl = MongoClient("localhost", 27017)
    db = cl.spotify
    col = db.recommendations

    vocabulary, cooccur = {}, {}

    for index, artist in enumerate(tqdm.tqdm(db.artists.find(), total=db.artists.estimated_document_count(),
                                             desc="Build Vocabulary")):
        vocabulary[artist["id"]] = {"name": artist["name"], "id": index}
        cooccur[index] = {}

    with open("vocabulary.pkl", 'wb') as file:
        pickle.dump(vocabulary, file)

    for recommendation in tqdm.tqdm(col.find(), total=col.estimated_document_count(), desc="Build Matrix"):
        for artist in recommendation["artists"]:
            try:
                for_id = vocabulary[recommendation["for"]]["id"]
                rec_id = vocabulary[artist]["id"]
                cooccur[rec_id].setdefault(for_id, 0.)
                cooccur[for_id].setdefault(rec_id, 0.)
                cooccur[rec_id][for_id] += 1
                cooccur[for_id][rec_id] += 1
            except KeyError:
                print(recommendation["for"])
                continue

    assert len(vocabulary) == len(cooccur)

    x = [len(v) for k, v in cooccur.items()]
    plt.title("Histogram - Amount of Recommendations per Artist")
    plt.xlabel("Amount of Recommendations")
    plt.ylabel("Amount Artists")
    plt.hist(x, bins=50, log=True)
    plt.show()

    with open("cooccurence.pkl", 'wb') as file:
        pickle.dump(cooccur, file)


if __name__ == "__main__":
    create_matrix()