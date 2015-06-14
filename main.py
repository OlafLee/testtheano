# coding=utf8
import theano.tensor as T
import theano
import cPickle, gzip, numpy
import matplotlib.pyplot as plt
from util import *
import time
import sys
import os

def shared_dataset(data_x, data_y):
    """ Function that loads the dataset into shared variables
The reason we store our dataset in shared variables is to allow
Theano to copy it into the GPU memory (when code is run on GPU).
Since copying data into the GPU is slow, copying a minibatch everytime
is needed (the default behaviour if the data is not in a shared
variable) would lead to a large decrease in performance.
    """
    shared_x = theano.shared(numpy.asarray(data_x, dtype=theano.config.floatX), borrow=True)  # @UndefinedVariable
    shared_y = theano.shared(numpy.asarray(data_y, dtype=theano.config.floatX), borrow=True)  # @UndefinedVariable
    return shared_x, T.cast(shared_y, 'int32')



if __name__ == '__main__':
    
    batch_size = 50  # size of the minibatch
    # accessing the third minibatch of the training set
    # Load the dataset
    f = gzip.open('mini_mnist.pkl.gz', 'rb')
    total_x = cPickle.load(f)
    total_y = cPickle.load(f)
    f.close()
    train_set_x, train_set_y = shared_dataset(total_x[:1000], total_y[:1000])
    valid_set_x, valid_set_y = shared_dataset(total_x[1000:1100], total_y[1000:1100])
    test_set_x, test_set_y = shared_dataset(total_x[1100:1200], total_y[1100:1200])
    data = train_set_x[2 * 50: 3 * 50]
    label = train_set_y[2 * 50: 3 * 50]
    '''
    for index, (image,label) in enumerate(zip(total_x[:8],total_y[:8])):
        
        plt.subplot(2, 4, index + 1)
        plt.axis('off')
        plt.imshow(image.reshape(28,28), cmap=plt.cm.gray_r, interpolation='nearest')  # @UndefinedVariable
        plt.title('Training: %i' % label)
    plt.show()
    '''
    
    n_train_batches = train_set_x.get_value(borrow=True).shape[0] / batch_size
    n_valid_batches = valid_set_x.get_value(borrow=True).shape[0] / batch_size
    n_test_batches = test_set_x.get_value(borrow=True).shape[0] / batch_size
    
    print '... building the model'

    # allocate symbolic variables for the data
    index = T.lscalar()  # index to a [mini]batch

    # generate symbolic variables for input (x and y represent a
    # minibatch)
    x = T.matrix('x')  # data, presented as rasterized images
    y = T.ivector('y')  # labels, presented as 1D vector of [int] labels

    # construct the logistic regression class
    # Each MNIST image has size 28*28
    classifier = LogisticRegression(input=x, n_in=28 * 28, n_out=10)

    # the cost we minimize during training is the negative log likelihood of
    # the model in symbolic format
    cost = classifier.negative_log_likelihood(y)

    # compiling a Theano function that computes the mistakes that are made by
    # the model on a minibatch
    test_model = theano.function(
        inputs=[index],
        outputs=classifier.errors(y),
        givens={
            x: test_set_x[index * batch_size: (index + 1) * batch_size],
            y: test_set_y[index * batch_size: (index + 1) * batch_size]
        }
    )
    
    print 'cost:'+theano.pp(cost)
    
    validate_model = theano.function(
        inputs=[index],
        outputs=classifier.errors(y),
        givens={
            x: valid_set_x[index * batch_size: (index + 1) * batch_size],
            y: valid_set_y[index * batch_size: (index + 1) * batch_size]
        }
    )

    # compute the gradient of cost with respect to theta = (W,b)
    g_W = T.grad(cost=cost, wrt=classifier.W)
    g_b = T.grad(cost=cost, wrt=classifier.b)
    
    learning_rate = 0.13
    n_epochs = 1000
    # start-snippet-3
    # specify how to update the parameters of the model as a list of
    # (variable, update expression) pairs.
    updates = [(classifier.W, classifier.W - learning_rate * g_W),
               (classifier.b, classifier.b - learning_rate * g_b)]

    # compiling a Theano function `train_model` that returns the cost, but in
    # the same time updates the parameter of the model based on the rules
    # defined in `updates`
    train_model = theano.function(
        inputs=[index],
        outputs=cost,
        updates=updates,
        givens={
            x: train_set_x[index * batch_size: (index + 1) * batch_size],
            y: train_set_y[index * batch_size: (index + 1) * batch_size]
        }
    )
    # end-snippet-3

    ###############
    # TRAIN MODEL #
    ###############
    print '... training the model'
    # early-stopping parameters
    patience = 100  # look as this many examples regardless
    patience_increase = 2  # wait this much longer when a new best is
                                  # found
    improvement_threshold = 0.995  # a relative improvement of this much is
                                  # considered significant
    validation_frequency = min(n_train_batches, patience / 2)
                                  # go through this many
                                  # minibatche before checking the network
                                  # on the validation set; in this case we
                                  # check every epoch

    best_validation_loss = numpy.inf
    test_score = 0.
    start_time = time.clock()

    done_looping = False
    epoch = 0
    while (epoch < n_epochs) and (not done_looping):
        epoch = epoch + 1
        for minibatch_index in xrange(n_train_batches):

            minibatch_avg_cost = train_model(minibatch_index)
            # iteration number
            iter = (epoch - 1) * n_train_batches + minibatch_index

            if (iter + 1) % validation_frequency == 0:
                # compute zero-one loss on validation set
                validation_losses = [validate_model(i)
                                     for i in xrange(n_valid_batches)]
                this_validation_loss = numpy.mean(validation_losses)

                print(
                    'epoch %i, minibatch %i/%i, validation error %f %%' % 
                    (
                        epoch,
                        minibatch_index + 1,
                        n_train_batches,
                        this_validation_loss * 100.
                    )
                )

                # if we got the best validation score until now
                if this_validation_loss < best_validation_loss:
                    # improve patience if loss improvement is good enough
                    if this_validation_loss < best_validation_loss * \
                       improvement_threshold:
                        patience = max(patience, iter * patience_increase)

                    best_validation_loss = this_validation_loss
                    # test it on the test set

                    test_losses = [test_model(i)
                                   for i in xrange(n_test_batches)]
                    test_score = numpy.mean(test_losses)

                    print(
                        (
                            '     epoch %i, minibatch %i/%i, test error of'
                            ' best model %f %%'
                        ) % 
                        (
                            epoch,
                            minibatch_index + 1,
                            n_train_batches,
                            test_score * 100.
                        )
                    )

            if patience <= iter:
                done_looping = True
                break

    end_time = time.clock()
    print(
        (
            'Optimization complete with best validation score of %f %%,'
            'with test performance %f %%'
        )
        % (best_validation_loss * 100., test_score * 100.)
    )
    print 'The code run for %d epochs, with %f epochs/sec' % (
        epoch, 1. * epoch / (end_time - start_time))
    print >> sys.stderr, ('The code for file ' + 
                          os.path.split(__file__)[1] + 
                          ' ran for %.1fs' % ((end_time - start_time)))
    
    test_whole = theano.function(
        inputs=[],
        outputs=classifier.errors(y),
        givens={
            x: test_set_x,
            y: test_set_y
        }
    )
    test_whole2 = theano.function(
        inputs=[x,y],
        outputs=classifier.errors(y),
    )
    
    print('total test score of %f %%' % (test_whole() * 100.))
    print('total test score of %f %%' % (test_whole2(total_x[1100:1200], total_y[1100:1200].astype('int32')) * 100.))
