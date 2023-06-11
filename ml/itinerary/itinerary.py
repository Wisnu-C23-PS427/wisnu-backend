import json
import pandas as pd
import numpy as np
import tensorflow as tf
from keras.models import load_model
from sklearn.feature_extraction.text import TfidfVectorizer
from math import radians, sin, cos, sqrt, atan2

def generate_itinerary(city_name, num_days):
    # Memuat dataset
    data = pd.read_csv('ml/itinerary/wisataindonesia.csv')

    # Pra-pemrosesan data
    data['provinsi'] = data['provinsi'].fillna('')

    # Melakukan vektorisasi TF-IDF pada fitur "kota" dan "provinsi"
    tfidf_kota = TfidfVectorizer()
    tfidf_provinsi = TfidfVectorizer()

    tfidf_matrix_kota = tfidf_kota.fit_transform(data['kota'])
    tfidf_matrix_provinsi = tfidf_provinsi.fit_transform(data['provinsi'])

    # Menggabungkan matriks TF-IDF
    tfidf_matrix = np.concatenate((tfidf_matrix_kota.toarray(), tfidf_matrix_provinsi.toarray()), axis=1)

    # Model
    model = load_model('ml/itinerary/recommendation_model.h5')

    # Mendapatkan embedding item
    item_embeddings = model.predict(tfidf_matrix)

    # Mendapatkan indeks item berdasarkan input kota
    def get_item_index_by_kota(kota, data):
        index = data[data['kota'] == kota].index
        return index[0] if len(index) > 0 else None

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

    # Merekomendasikan item berdasarkan kota dan durasi liburan yang diberikan
    def recommend_items(kota, durasi, item_embeddings, items=data[['attraction_id', 'nama', 'kota', 'id_kota', 'provinsi','longitude','latitude','img','total_rating', 'category', 'child_price', 'adult_price']], k=5):
        indeks_item = get_item_index_by_kota(kota, data)
        if indeks_item is None:
            return pd.DataFrame()  # Mengembalikan dataframe kosong jika kota tidak ditemukan

        vektor_item = item_embeddings[indeks_item]
        similarity_scores = np.dot(item_embeddings, vektor_item)
        indeks_terurut = np.argsort(similarity_scores)[::-1][:k]
        item_terrekomendasikan = items.iloc[indeks_terurut].copy()

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

    # Replace kota_input and durasi_input with the city_name and num_days arguments respectively
    item_terrekomendasikan = recommend_items(city_name, num_days, item_embeddings, items=data[['attraction_id', 'nama', 'kota', 'id_kota', 'provinsi','longitude','latitude','img','total_rating', 'category', 'child_price', 'adult_price']], k=20)

    if not item_terrekomendasikan.empty:
        output = item_terrekomendasikan.to_dict(orient='records')
        json_output = json.dumps(output)
        print(json_output)
        return json.loads(json_output)
    else:
        output = {'message': 'Tidak ada item yang ditemukan untuk kota yang diberikan.'}
        json_output = json.dumps(output)
        return json.loads(json_output)
