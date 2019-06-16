"""
```trial
2019-06-16 10:53:38
Test
[[dirty]]: 📚 documentation for examples
start_step: 0

---------------------------------------------------
| global_step | train_loss | test_loss | accuracy |
---------------------------------------------------
|         937 |       1.61 |      1.66 |     0.82 |
|       1,874 |       1.62 |      1.66 |     0.82 |
---------------------------------------------------
```
"""

import argparse

import tensorflow as tf

from lab.experiment.tensorflow import Experiment
from lab_globals import lab

# Declare the experiment
EXPERIMENT = Experiment(lab=lab,
                        name="mnist_tensorflow",
                        python_file=__file__,
                        comment="Test",
                        check_repo_dirty=False
                        )

logger = EXPERIMENT.logger


def create_mnist_dataset(data, labels, batch_size):
    def gen():
        for image, label in zip(data, labels):
            yield image, label

    ds = tf.data.Dataset.from_generator(gen, (tf.float32, tf.int32), ((28, 28), ()))

    return ds.shuffle(batch_size).batch(batch_size)


def loss(model, x, y):
    y_ = model(x)
    return tf.losses.sparse_softmax_cross_entropy(labels=y, logits=y_)


def accuracy(model, x, y):
    pred = tf.argmax(model(x), axis=1, output_type=tf.int32)
    correct = tf.equal(pred, y)
    return tf.reduce_mean(tf.dtypes.cast(correct, tf.float32))


def train(args, session: tf.Session, loss_value, train_op, batches, epoch):
    batch_idx = -1
    while True:
        batch_idx += 1
        try:
            l, _ = session.run([loss_value, train_op])
        except tf.errors.OutOfRangeError:
            break

        # Add training loss to the logger.
        # The logger will queue the values and output the mean
        logger.store(train_loss=l)

        # Print output to the console
        if batch_idx % args.log_interval == 0:
            # Reset the current line
            logger.clear_line(reset=True)
            # Print step
            logger.print_global_step(epoch * batches + batch_idx)
            # Output the indicators without a newline
            # because we'll be replacing the same line
            logger.write(global_step=epoch * batches + batch_idx, new_line=False)


def test(session: tf.Session, loss_value, accuracy_value, batches):
    test_loss = 0
    correct = 0
    while True:
        try:
            l, a = session.run([loss_value, accuracy_value])
            test_loss += l
            correct += a
        except tf.errors.OutOfRangeError:
            break

    logger.store(test_loss=test_loss / batches)
    logger.store(accuracy=correct / batches)


def parse_args():
    parser = argparse.ArgumentParser(description='PyTorch MNIST Example')
    parser.add_argument('--batch-size', type=int, default=64, metavar='N',
                        help='input batch size for training (default: 64)')
    parser.add_argument('--test-batch-size', type=int, default=1000, metavar='N',
                        help='input batch size for testing (default: 1000)')
    parser.add_argument('--epochs', type=int, default=10, metavar='N',
                        help='number of epochs to train (default: 10)')
    parser.add_argument('--lr', type=float, default=0.01, metavar='LR',
                        help='learning rate (default: 0.01)')
    parser.add_argument('--momentum', type=float, default=0.5, metavar='M',
                        help='SGD momentum (default: 0.5)')
    parser.add_argument('--no-cuda', action='store_true', default=False,
                        help='disables CUDA training')
    parser.add_argument('--seed', type=int, default=1, metavar='S',
                        help='random seed (default: 1)')
    parser.add_argument('--log-interval', type=int, default=10, metavar='N',
                        help='how many batches to wait before logging training status')

    parser.add_argument('--save-model', action='store_true', default=False,
                        help='For Saving the current Model')
    return parser.parse_args()


def main():
    args = parse_args()

    # Loading data
    with logger.monitor("Load data"):
        mnist = tf.keras.datasets.mnist

        (x_train, y_train), (x_test, y_test) = mnist.load_data()
        x_train, x_test = x_train / 255.0, x_test / 255.0

        train_dataset = create_mnist_dataset(x_train, y_train, args.batch_size)
        test_dataset = create_mnist_dataset(x_test, y_test, args.batch_size)

    # Model creation
    with logger.monitor("Create model"):
        model = tf.keras.models.Sequential([
            tf.keras.layers.Flatten(input_shape=(28, 28)),
            tf.keras.layers.Dense(512, activation=tf.nn.relu),
            tf.keras.layers.Dropout(0.2),
            tf.keras.layers.Dense(10, activation=tf.nn.softmax)
        ])

    # Creation of the trainer
    with logger.monitor("Create trainer"):
        optimizer = tf.train.AdamOptimizer(learning_rate=args.lr)
        train_iterator = train_dataset.make_initializable_iterator()
        data, target = train_iterator.get_next()
        train_loss = loss(model, data, target)
        train_op = optimizer.minimize(train_loss)

        test_iterator = test_dataset.make_initializable_iterator()
        data, target = test_iterator.get_next()
        test_loss = loss(model, data, target)
        test_accuracy = accuracy(model, data, target)

    logger.add_indicator("train_loss", queue_limit=10, is_print=True)
    logger.add_indicator("test_loss", is_histogram=False, is_print=True)
    logger.add_indicator("accuracy", is_histogram=False, is_print=True)

    # Create a monitored iterator
    monitor = logger.iterator(range(0, args.epochs))

    #
    batches = len(x_train) // args.batch_size

    with tf.Session() as session:
        EXPERIMENT.start_train(0, session)

        # Loop through the monitored iterator
        for epoch in monitor:
            global_step = (epoch + 1) * batches

            # Delayed keyboard interrupt handling to use
            # keyboard interrupts to end the loop.
            # This will capture interrupts and finish
            # the loop at the end of processing the iteration;
            # i.e. the loop won't stop in the middle of an epoch.
            try:
                with logger.delayed_keyboard_interrupt():

                    # Training and testing
                    session.run(train_iterator.initializer)
                    train(args, session, train_loss, train_op, batches, epoch)
                    session.run(test_iterator.initializer)
                    test(session, test_loss, test_accuracy, len(x_test) // args.batch_size)

                    # Output the progress summaries to `trial.yaml` and
                    # to the python file header
                    progress_dict = logger.get_progress_dict(
                        global_step=global_step)
                    EXPERIMENT.save_progress(progress_dict)

                    # Clear line and output to console
                    logger.clear_line(reset=True)
                    logger.print_global_step(global_step)
                    logger.write(global_step=global_step, new_line=False)

                    # Output the progress of the loop,
                    # time taken and time remaining
                    monitor.progress()

                    # Clear line and go to the next line;
                    # that is, we add a new line to the output
                    # at the end of each epoch
                    logger.clear_line(reset=False)

            # Handled delayed interrupt
            except KeyboardInterrupt:
                logger.clear_line(reset=False)
                logger.log("\nKilling loop...")
                break

    logger.clear_line(reset=False)


if __name__ == '__main__':
    main()