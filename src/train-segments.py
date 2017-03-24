#!/usr/bin/env python

import os
import sys
import re
import getopt
import psycopg2
from sklearn.externals import joblib
from sklearn.neighbors import KNeighborsClassifier
from sklearn.ensemble import GradientBoostingClassifier
from buildings import getInfo

'''
  load the relevance data and create the trained object for later
  classification prediction
'''


def Usage():
  print '''
Usage: train-segments.py <options> trained-object.pkl.gz
    -i|--info  - report available jobid, project, t, s, c parameters
    -b|--table tablename - table with relevance and class code
    -j|--jobid name    -+
    -p|--project name   |
    -m|--mode ir|tc|fc  |
    -t|--threshold n.n  |- filter dataset to be extracted
    -s|--shape n.n      |
    -c|--compact n.n   -+
    -r|--relevance n.n - min relevance value to be part of class, default: 0.5
    -v|--verbose
    -x|--test - Use 50% of data to train and 50% to predict and report
    -a|--algorithm - KNN - KNearestNeighbors|
                     GBT - Gradient Boost Tree, default: GBT
'''
  sys.exit(2)



def trainKNN(X, y):
  '''
     KNeighborsClassifier(n_neighbors=5, weights='uniform', algorithm='auto', leaf_size=30, p=2, metric='minkowski', metric_params=None, n_jobs=1, **kwargs)
     n_neighbors - number of neighbors to use by default for k_neighbors queries.
     weights = 'uniform'|'distance'|[callable]
     algorithm = 'auto'|'ball_tree'|'kd_tree'|'brute'
     leaf_size - Leaf size passed to BallTree or KDTree
     metric : string or DistanceMetric object (default = 'minkowski')
     p : integer - Power parameter for the Minkowski metric.
         When p = 1, this is equivalent to using manhattan_distance (l1),
         and euclidean_distance (l2) for p = 2.
         For arbitrary p, minkowski_distance (l_p) is used.
     metric_params : dict  optional (default = None)
         Additional keyword arguments for the metric function.
     n_jobs : int, optional (default = 1)
         The number of parallel jobs to run for neighbors search
         If -1, then the number of jobs is set to the number of CPU cores.
         Doesn't affect fit method.


    Methods:
    fit(X, y) - Fit the model using X as training data and y as target values
    get_params([deep]) - Get parameters for this estimator.
    kneighbors([X, n_neighbors, return_distance]) - Finds the K-neighbors of
                                                    a point.
    kneighbors_graph([X, n_neighbors, mode]) - Computes the (weighted) graph
                                               of k-Neighbors for points in X
    predict(X) - Predict the class labels for the provided data
    predict_proba(X) - Return probability estimates for the test data X.
    score(X, y[, sample_weight]) - Returns the mean accuracy on the giveni
                                   test data and labels.
    set_params(\*\*params) - Set the parameters of this estimator.

     http://scikit-learn.org/stable/modules/generated/sklearn.neighbors.KNeighborsClassifier.html
  '''

  cls = KNeighborsClassifier()
  cls.fit(X, y)

  return cls



def trainGBT( X, y ):
  '''
    sklearn.ensemble.GradientBoostingClassifier(
      loss='deviance',
      learning_rate=0.1,
      n_estimators=100,
      subsample=1.0,
      criterion='friedman_mse',
      min_samples_split=2,
      min_samples_leaf=1,
      min_weight_fraction_leaf=0.0,
      max_depth=3,
      min_impurity_split=1e-07,
      init=None,
      random_state=None,
      max_features=None,
      verbose=0,
      max_leaf_nodes=None,
      warm_start=False,
      presort='auto')

    loss : {'deviance', 'exponential'}, optional (default='deviance')
        loss function to be optimized. 'deviance' refers to deviance
        (= logistic regression) for classification with probabilistic outputs.
        For loss 'exponential' gradient boosting recovers the AdaBoost
        algorithm.
    learning_rate : float, optional (default=0.1)
        learning rate shrinks the contribution of each tree by learning_rate.
        There is a trade-off between learning_rate and n_estimators
    n_estimators : int (default=100)
        The number of boosting stages to perform. Gradient boosting is fairly
        robust to over-fitting so a large number usually results in better
        performance
    max_depth : integer, optional (default=3)
        maximum depth of the individual regression estimators. The maximum
        depth limits the number of nodes in the tree. Tune this parameter
        for best performance; the best value depends on the interaction of
        the input variables.
    criterion : string, optional (default='friedman_mse')
        The function to measure the quality of a split. Supported criteria
        are 'friedman_mse' for the mean squared error with improvement score
        by Friedman, 'mse' for mean squared error, and 'mae' for the mean
        absolute error. The default value of 'friedman_mse' is generally
        the best as it can provide a better approximation in some cases.
    min_samples_split : int, float, optional (default=2)
        The minimum number of samples required to split an internal node:
          If int, then consider min_samples_split as the minimum number.
          If float, then min_samples_split is a percentage and
            ceil(min_samples_split * n_samples) are the minimum number of
            samples for each split.
    min_samples_leaf : int, float, optional (default=1)
        The minimum number of samples required to be at a leaf node:
          If int, then consider min_samples_leaf as the minimum number.
          If float, then min_samples_leaf is a percentage and
            ceil(min_samples_leaf * n_samples) are the minimum number of
            samples for each node.
    min_weight_fraction_leaf : float, optional (default=0.)
        The minimum weighted fraction of the sum total of weights (of all
        the input samples) required to be at a leaf node. Samples have equal
        weight when sample_weight is not provided.
    subsample : float, optional (default=1.0)
        The fraction of samples to be used for fitting the individual base
        learners. If smaller than 1.0 this results in Stochastic Gradient
        Boosting. subsample interacts with the parameter n_estimators.
        Choosing subsample < 1.0 leads to a reduction of variance and an
        increase in bias.
    max_features : int, float, string or None, optional (default=None)
        The number of features to consider when looking for the best split:
          If int, then consider max_features features at each split.
          If float, then max_features is a percentage and
            int(max_features * n_features) features are considered at
            each split.
          If 'auto', then max_features=sqrt(n_features).
          If 'sqrt', then max_features=sqrt(n_features).
          If 'log2', then max_features=log2(n_features).
          If None, then max_features=n_features.
        Choosing max_features < n_features leads to a reduction of variance
        and an increase in bias.
        Note: the search for a split does not stop until at least one valid
        partition of the node samples is found, even if it requires to
        effectively inspect more than max_features features.
    max_leaf_nodes : int or None, optional (default=None)
        Grow trees with max_leaf_nodes in best-first fashion. Best nodes are
        defined as relative reduction in impurity. If None then unlimited
        number of leaf nodes.
    min_impurity_split : float, optional (default=1e-7)
        Threshold for early stopping in tree growth. A node will split if
        its impurity is above the threshold, otherwise it is a leaf.
    init : BaseEstimator, None, optional (default=None)
        An estimator object that is used to compute the initial predictions.
        init has to provide fit and predict.
        If None it uses loss.init_estimator.
    verbose : int, default: 0
        Enable verbose output. If 1 then it prints progress and performance
        once in a while (the more trees the lower the frequency). If greater
        than 1 then it prints progress and performance for every tree.
    warm_start : bool, default: False
        When set to True, reuse the solution of the previous call to fit and
        add more estimators to the ensemble, otherwise, just erase the
        previous solution.
    random_state : int, RandomState instance or None, optional (default=None)
        If int, random_state is the seed used by the random number generator;
        If RandomState instance, random_state is the random number generator;
        If None, the random number generator is the RandomState instance used
        by np.random.
    presort : bool or 'auto', optional (default='auto')
        Whether to presort the data to speed up the finding of best splits
        in fitting. Auto mode by default will use presorting on dense data
        and default to normal sorting on sparse data. Setting presort to true
        on sparse data will raise an error.

    http://scikit-learn.org/stable/modules/generated/sklearn.ensemble.GradientBoostingClassifier.html
  '''

  cls = GradientBoostingClassifier(n_estimators=100, learning_rate=1.0,
      max_depth=1, random_state=0)
  cls.fit( X, y )

  return cls




def Main(argv):

  table = ''
  jobid = ''
  project = ''
  mode = ''
  threshold = ''
  shape = ''
  compact = ''
  relevance = 0.5
  verbose = False
  test = False
  algorithm = 'KNN'
  do_info = False

  try:
    opts, args = getopt.getopt(argv, 'hib:j:p:m:t:s:c:r:vxa:', ['help', 'table', 'jobid', 'project', 'mode', 'threshold', 'shape', 'compact', 'relevance', 'verbose', 'test', 'algorithm'])
  except:
    Usage()

  for opt, arg in opts:
    if opt == '--help':
      Usage()
    elif opt in ('-v', '--verbose'):
      verbose = True
    elif opt in ('-i', '--info'):
      do_info = True
    elif opt in ('-b', '--table'):
      table = re.sub(r'[^a-zA-Z0-9_]', '', arg)
    elif opt in ('-j', '--jobid'):
      jobid = arg
    elif opt in ('-p', '--project'):
      project = arg
    elif opt in ('-m', '--mode'):
      mode = arg
    elif opt in ('-t', '--threshold'):
      threshold = arg
    elif opt in ('-s', '--shape'):
      shape = arg
    elif opt in ('-c', '--compact'):
      compact = arg
    elif opt in ('-r', '--relevance'):
      relevance = float(arg)
    elif opt in ('-x', '--test'):
      test = True
    elif opt in ('-a', '--algorithm'):
      if arg in ('KNN', 'GBT'):
        algorithm = arg
      else:
        print 'ERROR: invalid algorithm (%s)' % (arg)
        Usage()

  if do_info:
    getInfo(mode, jobid, project)

  if len(table) == 0:
    print "ERROR: -b|--table is a required parameter."
    sys.exit(1)

  if not test and len(args) != 1:
    print "ERROR: extra args or missing trained-object.pkl.gz param!"
    sys.exit(1)

  try:
    conn = psycopg2.connect("dbname=ma_buildings")
  except:
    print "ERROR: failed to connect to database 'ma_buildings'"
    sys.exit(1)

  conn.set_session(autocommit=True)
  cur = conn.cursor()

  ptable = 'seg_polys'
  if mode != '':
    ptable = 'seg_polys_' + mode

  # fetch data for X, y arrays
  sql = '''select
   area,
   b0_max,
   b0_mean,
   b0_min,
   b0_std,
   b1_max,
   b1_mean,
   b1_min,
   b1_std,
   b2_max,
   b2_mean,
   b2_min,
   b2_std,
   b3_max,
   b3_mean,
   b3_min,
   b3_std,'''
  if mode in ('4b', '5b'):
    sql = sql + '''
   b4_max,
   b4_mean,
   b4_min,
   b4_std,'''
  if mode == '5b':
    sql = sql + '''
   b5_max,
   b5_mean,
   b5_min,
   b5_std,'''
  sql = sql + '''
   bperim,
   compact,
   frac,
   para,
   perimeter,
   shape,
   smooth,
   dist2road,
   a.gid,
   case when pctoverlap>=%f then class else 0 end as pclass
from sd_data."%s" a, relevance."%s" b
where a.gid=b.gid '''

  sql = sql % ( relevance, ptable, table )

  where = []
  if jobid != '':     where.append(" jobid='%s' "   % ( jobid ))
  if project != '':   where.append(" project='%s' " % ( project ))
  if mode != '':      where.append(" mode='%s' "    % ( mode ))
  if threshold != '': where.append(" t=%f "         % ( float(threshold) ))
  if shape != '':     where.append(" s=%f "         % ( float(shape) ))
  if compact != '':   where.append(" c=%f "         % ( float(compact) ))
  if len(where) > 0:
    sql = sql + ' and ' + ' and '.join(where)
  sql = sql + ' order by gid'

  cur.execute( sql )

  X = []
  y = []
  gid = []
  for row in cur:
    X.append(row[:-2])
    y.append(row[-1])
    gid.append(row[-2])

  if verbose:
    print "X = ", X
    print "y = ", y

  if test:
    N = int(len(X) / 2)
    print "Train data:"
    print "  Count of class 2: ", y[:N].count(2)
    print "  Count of class 1: ", y[:N].count(1)
    print "  Count of class 0: ", y[:N].count(0)

    print "Test data:"
    print "  Count of class 2: ", y[N:].count(2)
    print "  Count of class 1: ", y[N:].count(1)
    print "  Count of class 0: ", y[N:].count(0)

    if algorithm == 'KNN':
      classifier = trainKNN( X[:N], y[:N] )
    else:
      classifier = trainGBT( X[:N], y[:N] )

    score = classifier.score( X[N:], y[N:] )
    print "Score:", score
    #print "Proba:", classifier.predict_proba( X[N:] )

    pclass = classifier.predict(  X[N:] )
    print "Predict class count:"
    print "  Count of class 2: ", pclass.tolist().count(2)
    print "  Count of class 1: ", pclass.tolist().count(1)
    print "  Count of class 0: ", pclass.tolist().count(0)

    '''
       Save test results back to the DB so we can view them on the map
    '''

    sql = 'create schema if not exists testresults'
    cur.execute( sql )

    sql = 'drop table if exists testresults."%s" cascade' % ( table )
    cur.execute( sql )

    sql = '''create table testresults."%s" (
  gid integer not null primary key,
  train integer,
  class integer) ''' % ( table )
    cur.execute( sql )

    for i in range(len(y)):
      sql = '''insert into testresults."%s" values (%d, %d, %d) ''' % ( table, gid[i], 1 if i<N else 0, y[i] if i<N else pclass[i-N] )
      cur.execute( sql )


  else:
    if algorithm == 'KNN':
      classifier = trainKNN( X, y )
    else:
      classifier = trainGBT( X, y )
    joblib.dump( classifier, args[0] )
    print "Trained %s Classifier saved as: %s" % ( algorithm, args[0] )

  conn.close()


  '''
  import pickle
  pfile = 'test-%s.pkl' % ( algorithm )
  fh = open(pfile, 'wb')
  pickle.dump(classifier, fh)
  fh.close()
  '''

if len(sys.argv) == 1:
  Usage()

if __name__ == '__main__':
  Main(sys.argv[1:])

