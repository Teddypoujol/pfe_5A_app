#!/usr/bin/env python
# coding: utf-8
from __future__ import unicode_literals, print_function
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
import random
from pathlib import Path
import thinc.extra.datasets
import spacy
from spacy.util import minibatch, compounding

from flask import Flask, render_template, request,jsonify, json, g
from flask_cors import CORS, cross_origin


app = Flask(__name__)
cors = CORS(app, resources={r"/*": {"origins": "*"}})
app.config['CORS_HEADERS'] = 'Content-Type'
app.config['CORS_HEADERS'] = 'Access-Control-Allow-Origin'


# Charge le csv et etudie le type pour connaitre le % de l'introvertion, intuition, reflexion et jugement
def load_data(train_data,limit=0, split=0.8):
    """Load data from the IMDB dataset."""
    # Partition off part of the train data for evaluation
    #random.shuffle(train_data)
    train_data = train_data[-limit:]
    Y,X = train_data["type"], train_data["posts"]
    y = []
    for y_ in Y:
        if y_[0] == 'I' : INTROVERTED = True
        else: INTROVERTED = False
        if y_[1] == 'N' : INTUTIVE=  True
        else: INTUTIVE=  False
        if y_[2] == 'T' : THINKING=  True
        else: THINKING= False
        if y_[3] == 'J' : JUDGEMENTAL=  True
        else: JUDGEMENTAL=  False
        y.append({'INTROVERTED':INTROVERTED,"INTUTIVE":INTUTIVE,"THINKING":THINKING,"JUDGEMENTAL":JUDGEMENTAL})
            
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=split, random_state=42)
    return (X_train, y_train), (X_test, y_test)

#Fonction evaluation du model
def evaluate(tokenizer, textcat, texts, cats):
    docs = (tokenizer(text) for text in texts)
    tp = 1e-8  # True positives
    fp = 1e-8  # False positives
    fn = 1e-8  # False negatives
    tn = 1e-8  # True negatives
    for i, doc in enumerate(textcat.pipe(docs)):
        gold = cats[i]
        for label, score in doc.cats.items():
            if label not in gold:
                continue
            if score >= 0.5 and gold[label] >= 0.5:
                tp += 1.
            elif score >= 0.5 and gold[label] < 0.5:
                fp += 1.
            elif score < 0.5 and gold[label] < 0.5:
                tn += 1
            elif score < 0.5 and gold[label] >= 0.5:
                fn += 1
    precision = tp / (tp + fp)
    recall = tp / (tp + fn)
    f_score = 2 * (precision * recall) / (precision + recall)
    return {'textcat_p': precision, 'textcat_r': recall, 'textcat_f': f_score}



# Entrainement du model, ou creation du model
def entrainement(model=None, output_dir=None, n_iter=20, n_texts=2000):
    df = pd.read_csv("mbti_1.csv")
    if model is not None:
        nlp = spacy.load(model)  # load existing spaCy model
        print("Loaded model '%s'" % model)
    else:
        nlp = spacy.blank('en')  # create blank Language class
        print("Created blank 'en' model")

    # add the text classifier to the pipeline if it doesn't exist
    # nlp.create_pipe works for built-ins that are registered with spaCy
    if 'textcat' not in nlp.pipe_names:
        textcat = nlp.create_pipe('textcat')
        nlp.add_pipe(textcat, last=True)
    # otherwise, get it, so we can add labels to it
    else:
        textcat = nlp.get_pipe('textcat')

    # add label to text classifier
    textcat.add_label('INTROVERTED')
    textcat.add_label('INTUTIVE')
    textcat.add_label('JUDGEMENTAL')
    textcat.add_label('THINKING')

    # load the IMBD dataset
    print("Loading MBTI data...")
    (train_texts, train_cats), (dev_texts, dev_cats) = load_data(df,limit=n_texts)
    print("Using {} examples ({} training, {} evaluation)"
        .format(n_texts, len(train_texts), len(dev_texts)))
    train_data = list(zip(train_texts,
                        [{'cats': cats} for cats in train_cats]))

    # get names of other pipes to disable them during training
    other_pipes = [pipe for pipe in nlp.pipe_names if pipe != 'textcat']
    with nlp.disable_pipes(*other_pipes):  # only train textcat
        optimizer = nlp.begin_training()
        print("Training the model...")
        print('{:^5}\t{:^5}\t{:^5}\t{:^5}'.format('LOSS', 'P', 'R', 'F'))
        for i in range(n_iter):
            losses = {}
            # batch up the examples using spaCy's minibatch
            batches = minibatch(train_data, size=compounding(4., 32., 1.001))
            for batch in batches:
                texts, annotations = zip(*batch)
                nlp.update(texts, annotations, sgd=optimizer, drop=0.2,
                        losses=losses)
            with textcat.model.use_params(optimizer.averages):
                # evaluate on the dev data split off in load_data()
                scores = evaluate(nlp.tokenizer, textcat, dev_texts, dev_cats)
            print('{0:.3f}\t{1:.3f}\t{2:.3f}\t{3:.3f}'  # print a simple table
                .format(losses['textcat'], scores['textcat_p'],
                        scores['textcat_r'], scores['textcat_f']))
        

def prediction(model=None, text=None):
    # test the trained model
    test_text = text
    # test the saved model
    print("Loading from", model)
    nlp2 = spacy.load(model)
    doc2 = nlp2(test_text)
    #print(test_text, doc2.cats)
    return doc2.cats

@app.route('/prediction', methods=['GET'])
@cross_origin(origin='*',headers=['Content- Type', 'Authorization', 'Access-Control-Allow-Origin'])
def donnerPersonnalite():
    print("test predict") 
    data = request.args.get('text')
    df = pd.read_csv("mbti_1.csv")
    load_data(df)
    #entrainement(output_dir="./model")
    #f = open("text.txt", "r") 
    js = prediction(model="./model", text=data)

    INTRO="E"
    INTUITION="S"
    JUGEMENT="P"
    REFLEXION="F"

    if js["INTROVERTED"] >= 0.5:
        INTRO="I"
    
    if js["INTUTIVE"] >= 0.5:
        INTUITION="N"
    
    if js["JUDGEMENTAL"] >= 0.5:
        JUGEMENT="J"
    
    if js["THINKING"] >= 0.5:
        REFLEXION="T"

    Personnalite=INTRO+INTUITION+REFLEXION+JUGEMENT
    print(Personnalite)
    js["PERSONNALITE"]=Personnalite
    js.headers.add('Access-Control-Allow-Origin', '*')
    return js

#print(lancement())

app.run(debug=True)