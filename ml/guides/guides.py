# import libraries
import numpy as np
import pandas as pd
import tensorflow as tf
from keras.models import load_model
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

def guides_recommendation(tempat_input):
    # get data
    data = pd.read_csv('ml/guides/local_guide.csv')

    # create object TfidfVectorizer
    vectorizer = TfidfVectorizer()

    # Melakukan vektorisasi TF-IDF pada fitur "Tempat"
    tfidf_matrix_tempat = vectorizer.fit_transform(data['Tempat'])

    # Mengubah matriks TF-IDF menjadi array
    tfidf_matrix = tfidf_matrix_tempat.toarray()

    # loads model
    model = load_model('ml/guides/model_local_guide.h5')

    # Merekomendasikan item berdasarkan Tempat
    def recommend_items(tempat, tfidf_matrix, model, items=data[['Pemandu_ID', 'Nama_Pemandu', 'Optional_Bahasa', 'Umur', 'Jenis_Kelamin', 'Tempat', 'Pendidikan_Terakhir', 'Pekerjaan', 'Nomor_Telepon', 'Price_per_hour', 'Time_duration_in_min', 'Avatars', 'Rating']], k=5):
        # Mendapatkan indeks item berdasarkan input Tempat
        def get_item_index_by_tempat(tempat, data):
            index = data[data['Tempat'] == tempat].index
            return index[0] if len(index) > 0 else None

        indeks_item = get_item_index_by_tempat(tempat, data)
        if indeks_item is None:
            return []  # Mengembalikan list kosong jika Tempat tidak ditemukan

        item_embedding = tfidf_matrix[indeks_item]
        item_embedding = np.reshape(item_embedding, (1, -1))

        similarity_scores = cosine_similarity(tfidf_matrix, item_embedding)
        similarity_scores = similarity_scores.flatten()

        indeks_terurut = np.argsort(similarity_scores)[::-1][:k]
        item_terrekomendasikan = items.iloc[indeks_terurut].copy()  # Add .copy() here

        # Mengurutkan berdasarkan Tempat terbaik
        item_terrekomendasikan = item_terrekomendasikan.sort_values('Tempat', ascending=False)

        # Prediksi menggunakan model
        item_embedding_pred = model.predict(item_embedding)
        similarity_scores_pred = cosine_similarity(tfidf_matrix, item_embedding_pred)
        similarity_scores_pred = similarity_scores_pred.flatten()

        indeks_terurut_pred = np.argsort(similarity_scores_pred)[::-1][:k]
        item_terrekomendasikan_pred = items.iloc[indeks_terurut_pred].copy()  # Add .copy() here

        # Mengurutkan berdasarkan Tempat terbaik
        item_terrekomendasikan_pred = item_terrekomendasikan_pred.sort_values('Tempat', ascending=False)

        # Convert the recommended items to a list of dictionaries
        return item_terrekomendasikan_pred

    item_terrekomendasikan = recommend_items(tempat_input, tfidf_matrix, model)

    return item_terrekomendasikan
