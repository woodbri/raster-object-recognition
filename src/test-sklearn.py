#!/usr/bin/env python

from sklearn import svm
from sklearn import datasets

clf = svm.SVC()
iris = datasets.load_iris()
X, y = iris.data, iris.target
clf.fit(X, y)
clf.predict(X[0:1])
print y[0]

import pickle
s = pickle.dumps(clf)
#print s
print
print X
print
print y

