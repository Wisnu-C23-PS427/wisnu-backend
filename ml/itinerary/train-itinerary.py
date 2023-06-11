#YANG pake cosine similarity
import pandas as pd
import numpy as np
import tensorflow as tf
from keras.models import Model
from keras.layers import Input, Dense
from keras.optimizers import Adam
from sklearn.feature_extraction.text import TfidfVectorizer
from datetime import datetime
import pickle
from sklearn.metrics.pairwise import cosine_similarity

# Menghapus sesi TensorFlow sebelumnya
tf.keras.backend.clear_session()

# Memuat dataset
data = pd.read_csv('ml/itinerary/wisataindonesia.csv')

# Pra-pemrosesan data
data['kota'] = data['kota'].fillna('Unknown')
data['provinsi'] = data['provinsi'].fillna('')

# Melakukan vektorisasi TF-IDF pada fitur "kota" dan "provinsi"
tfidf_kota = TfidfVectorizer()
tfidf_provinsi = TfidfVectorizer()

tfidf_matrix_kota = tfidf_kota.fit_transform(data['kota'])
tfidf_matrix_provinsi = tfidf_provinsi.fit_transform(data['provinsi'])

# Menggabungkan matriks TF-IDF
tfidf_matrix = np.concatenate((tfidf_matrix_kota.toarray(), tfidf_matrix_provinsi.toarray()), axis=1)
with open('tfidf_matrix.pickle', 'wb') as file:
    pickle.dump(tfidf_matrix, file)

# # Membangun model rekomendasi
input_shape = tfidf_matrix.shape[1]
input_layer = Input(shape=(input_shape,))
hidden_layer = Dense(128, activation='relu')(input_layer)
output_layer = Dense(input_shape, activation='linear')(hidden_layer)

model = Model(inputs=input_layer, outputs=output_layer)

# Membangun model rekomendasi
# input_shape = tfidf_matrix.shape[1]
# model = Sequential()
# model.add(Dense(128, activation='relu', input_shape=(input_shape,)))
# model.add(Dense(input_shape, activation='linear'))
model.compile(loss='cosine_similarity', optimizer=Adam(learning_rate=0.001))

# Melatih model
model.fit(tfidf_matrix, tfidf_matrix, epochs=10, batch_size=32)

# Pickle model
# with open('recommendation_model.pkl', 'wb') as f:
#     pickle.dump(model, f)

# Mendapatkan embedding item
model.save('ml/itinerary/recommendation_model.h5')

# Mendapatkan indeks item berdasarkan input kota
def get_item_index_by_kota(kota, data):
    index = data[data['kota'] == kota].index
    return index[0] if len(index) > 0 else None

from math import radians, sin, cos, sqrt, atan2

# Menghitung jarak antara dua titik berdasarkan lintang dan bujur formula haversine
def calculate_distance(lat1, lon1, lat2, lon2):
    R = 6371  # Jari-jari bumi dalam kilometer

    lat1_rad = radians(lat1)
    lon1_rad = radians(lon1)
    lat2_rad = radians(lat2)
    lon2_rad = radians(lon2)

    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad

    a = sin(dlat/2) ** 2 + cos(lat1_rad) * cos(lat2_rad) * sin(dlon/2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1-a))

    distance = R * c
    return distance

import random

# Merekomendasikan item berdasarkan kota dan durasi liburan yang diberikan
def recommend_items(kota, durasi, items=data[['attraction_id', 'nama', 'kota', 'id_kota', 'provinsi','longitude','latitude','img','total_rating']], k=5):
    indeks_item = get_item_index_by_kota(kota, data)
    if indeks_item is None:
        return pd.DataFrame()  # Mengembalikan dataframe kosong jika kota tidak ditemukan
    item_embedding = tfidf_matrix[indeks_item]
    item_embedding = np.reshape(item_embedding, (1, -1))
    
    item_embedding_pred = model.predict(item_embedding)
    similarity_scores_pred = cosine_similarity(tfidf_matrix, item_embedding_pred)
    similarity_scores = similarity_scores_pred.flatten()

    # Tambahkan faktor acak pada similarity_scores
    random_factor = np.random.normal(0, 0.01, size=similarity_scores.shape)
    similarity_scores += random_factor

    indeks_terurut = np.argsort(similarity_scores)[::-1][:k]
    item_terrekomendasikan = items.iloc[indeks_terurut].copy()  # Add .copy() here

    # Pengurutan acak item_terrekomendasikan
    item_terrekomendasikan = item_terrekomendasikan.sample(frac=1, random_state=42)

    # Membagi item terrekomendasikan secara merata berdasarkan durasi liburan
    jumlah_terrekomendasikan = len(item_terrekomendasikan)
    jumlah_hari = durasi
    item_per_hari = jumlah_terrekomendasikan // jumlah_hari
    sisa = jumlah_terrekomendasikan % jumlah_hari

    alokasi_hari = [item_per_hari] * jumlah_hari
    for i in range(sisa):
        alokasi_hari[i] += 1

    item_terrekomendasikan['hari'] = np.repeat(range(1, jumlah_hari + 1), alokasi_hari)[:jumlah_terrekomendasikan]
    item_terrekomendasikan = item_terrekomendasikan.sort_values('hari')

    # Batasi jumlah atraksi per hari menjadi 3
    item_terrekomendasikan = item_terrekomendasikan.groupby('hari').head(3)

    # Menghitung jarak antara atraksi dan kota yang diberikan
    lintang_kota = items.loc[indeks_item, 'latitude']
    bujur_kota = items.loc[indeks_item, 'longitude']
    item_terrekomendasikan['jarak'] = item_terrekomendasikan.apply(
        lambda row: calculate_distance(row['latitude'], row['longitude'], lintang_kota, bujur_kota),
        axis=1
    )
    item_terrekomendasikan = item_terrekomendasikan.sort_values('jarak')

    return item_terrekomendasikan



kota_input = 'Kabupaten Bantul'  # Ganti dengan input kota yang diinginkan
durasi_input = 10# Ganti dengan durasi liburan yang diinginkan

item_terrekomendasikan = recommend_items(kota_input, durasi_input,items=data[['attraction_id', 'nama', 'kota', 'id_kota', 'provinsi','longitude','latitude','img','total_rating','category','adult_price','child_price']], k=20)
if not item_terrekomendasikan.empty:
    item_terrekomendasikan.to_csv('recommended_items.csv', index=False)
    print('Item yang direkomendasikan disimpan ke recommended_items.csv')
else:
    print('Tidak ada item yang ditemukan untuk kota yang diberikan.')