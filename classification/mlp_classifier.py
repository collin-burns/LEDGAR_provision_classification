"""
Keras MLP classifier for provision classification using TF IDF weighted averaged MUSE embeddings
"""

import json
import random; random.seed(42)
import numpy; numpy.random.seed(42)
import tensorflow.keras as keras
from typing import List
from collections import Counter
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Dropout, Dense
from tensorflow.keras.callbacks import EarlyStopping, TensorBoard
from sklearn.preprocessing import MultiLabelBinarizer
from utils import embed, SplitDataSet, split_corpus, stringify_labels, \
    evaluate_multilabels, tune_clf_thresholds


def build_model(x_train, num_classes):
    print('Building model...')
    input_shape = x_train[0].shape[0]
    hidden_size_1 = input_shape * 2
    hidden_size_2 = int(input_shape / 2)
    model = Sequential()
    model.add(Dense(hidden_size_1, input_shape=(input_shape,), kernel_initializer=keras.initializers.glorot_uniform(seed=42), activation='relu'))
    model.add(Dropout(0.5, seed=42))
    model.add(Dense(hidden_size_2, kernel_initializer=keras.initializers.glorot_uniform(seed=42), activation='relu'))
    model.add(Dropout(0.5, seed=42))
    model.add(Dense(num_classes, kernel_initializer=keras.initializers.glorot_uniform(seed=42), activation='sigmoid'))
    model.compile(loss='binary_crossentropy', optimizer='adam', metrics=['accuracy'])
    print(model.summary())
    return model


if __name__ == '__main__':

    train_de = True
    test_de = True
    test_nda = False

    model_name = 'MLP_avg_NDA.h5'
    # model_name = 'MLP_avg_tfidf_NDA.h5'
    corpus_file = '../sec_corpus_2016-2019_clean_NDA_PTs2.jsonl'
    # model_name = 'MLP_avg_proto.h5'
    # corpus_file = '../sec_corpus_2016-2019_clean_proto.jsonl'

    epochs = 50
    batch_size = 32

    print('Loading corpus', corpus_file)
    dataset: SplitDataSet = split_corpus(corpus_file)
    print(len(dataset.y_train), 'training samples')
    print(len(dataset.y_test), 'test samples')
    print(len(dataset.y_dev), 'dev samples')

    mlb = MultiLabelBinarizer().fit(dataset.y_train)
    num_classes = mlb.classes_.shape[0]
    train_y = mlb.transform(dataset.y_train)
    test_y = mlb.transform(dataset.y_test)
    dev_y = mlb.transform(dataset.y_dev)

    embedding_file = '/home/don/resources/fastText_MUSE/wiki.multi.en.vec_data.npy'
    vocab_file = '/home/don/resources/fastText_MUSE/wiki.multi.en.vec_vocab.json'
    embeddings = numpy.load(embedding_file)
    vocab_en = json.load(open(vocab_file))
    print('Preprocessing')
    train_x = embed(dataset.x_train, embeddings, vocab_en, use_tfidf=True, avg_method='mean')
    test_x = embed(dataset.x_test, embeddings, vocab_en, use_tfidf=True, avg_method='mean')
    dev_x = embed(dataset.x_dev, embeddings, vocab_en, use_tfidf=True, avg_method='mean')

    # Calculate class weights
    all_labels: List[str] = [l for labels in dataset.y_train for l in labels]
    label_counts = Counter(all_labels)
    sum_labels_counts = sum(label_counts.values())
    class_weight = {numpy.where(mlb.classes_ == label)[0][0]:
                        1 - (cnt/sum_labels_counts)
                    for label, cnt in label_counts.items()}

    if train_de:
        model = build_model(train_x, num_classes)
        early_stopping = EarlyStopping(monitor='val_loss',
                                       patience=3, restore_best_weights=True)
        tensor_board = TensorBoard()
        print('Train model...')
        model.fit(train_x, train_y, batch_size=batch_size, epochs=epochs,
                  verbose=1, validation_data=(dev_x, dev_y),
                  class_weight=class_weight,
                  callbacks=[early_stopping, tensor_board])
        model.save('saved_models/%s' % model_name, overwrite=True)

    else:
        print('Loading model')
        model = keras.models.load_model('saved_models/%s' % model_name)

    y_pred_bin_dev = model.predict(dev_x)
    label_threshs = tune_clf_thresholds(y_pred_bin_dev, dataset.y_dev, mlb)
    y_pred_bin = model.predict(test_x)
    y_pred_thresh = stringify_labels(y_pred_bin, mlb, label_threshs=label_threshs)
    y_pred_nothresh = stringify_labels(y_pred_bin, mlb)
    print('MLP results without classifier threshold tuning')
    evaluate_multilabels(dataset.y_test, y_pred_nothresh, do_print=True)
    print('MLP results with classifier threshold tuning')
    evaluate_multilabels(dataset.y_test, y_pred_thresh, do_print=True)

    if test_nda:
        nda_file = '../nda_proprietary_data_sampled.jsonl'
        print('Loading corpus from', nda_file)
        dataset_nda: SplitDataSet = split_corpus(nda_file)
        nda_x = dataset_nda.x_train + dataset_nda.x_test + dataset_nda.x_dev
        nda_y = dataset_nda.y_train + dataset_nda.y_test + dataset_nda.y_dev
        nda_x_vecs = embed(nda_x, embeddings, vocab_en, use_tfidf=True, avg_method='mean')
        nda_y_vecs = mlb.transform(nda_y)
        y_preds_nda_probs = model.predict(nda_x_vecs)
        y_preds_nda = stringify_labels(y_preds_nda_probs, mlb, label_threshs=label_threshs)
        y_preds_nda_nothresh = stringify_labels(y_preds_nda_probs, mlb)
        print('MLP results NDA without classifier threshold tuning')
        evaluate_multilabels(nda_y, y_preds_nda_nothresh, do_print=True)
        print('MLP results NDA with classifier threshold tuning')
        evaluate_multilabels(nda_y, y_preds_nda, do_print=True)