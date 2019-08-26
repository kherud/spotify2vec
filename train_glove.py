from glove import *
import pickle
import numpy as np
import matplotlib.pyplot as plt

DIM = 100

with open("cooccurence.pkl", "rb") as file:
    cooccur = pickle.load(file)

model = Glove(cooccur, d=DIM, alpha=0.75, x_max=100.0)

print(model.W.shape)

errs = []
for epoch in range(25):
    err = model.train(batch_size=200, workers=16)  # , verbose=True
    print(f"epoch {epoch+1}, error {err}")
    errs.append(err)

plt.plot(errs)
plt.title("Train History")
plt.xlabel("Epoch")
plt.ylabel("Error")
plt.show()

np.save("glove-weights.npy", model.W)
