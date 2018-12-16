import csv
import os


def _read_meta_batch(outfile, batch_name_stub):

    batch_dirs = [os.getcwd() + "/Results/" + path for path in os.listdir('Results/') if batch_name_stub in path]
    summary_files = [path + "/" + path.split("/")[-1] + "_summary.csv" for path in batch_dirs]
    print(summary_files)
    with open(outfile, 'w') as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(["name", "status", "area", "response_time", "responder_speed", "responder_buffer", "threshold",
                         "responders"])
        for threshold in range(90, 100, 1):
            results = []
            for file in summary_files:
                with open(file, 'r') as csvfile:
                    spamreader = csv.reader(csvfile, delimiter=',', )
                    next(spamreader)
                    for row in spamreader:
                        if int(row[6]) == threshold:
                            results.append(row[-1])
            print(results)
            writer.writerow(results)


_read_meta_batch("Results/n_darts_highT_summary".format(), "n_darts_highT_test")


