import decimal
import demjson
import json
import logging
import hashlib
import numbers
import sys
import jsonlines


class DecimalJSONEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, decimal.Decimal):
            return str(o)
        return super(DecimalJSONEncoder, self).default(o)


class Measurement(object):
    def __init__(self, timeseries_id, timeseries_element):
        self.date = timeseries_element[0]
        if len(timeseries_element) <= 2:
            self.value = timeseries_element[1]
        else:
            self.value = timeseries_element[1:]
        self.doc_id = self.get_doc_id(timeseries_element)
        self.timeseries_id = timeseries_id

    def get_doc_id(self, array):
        array_str = json.dumps(array, cls=DecimalJSONEncoder)
        hash_object = hashlib.sha1(array_str)
        return hash_object.hexdigest()

    def to_dict(self):
        dct = {}
        dct['date'] = self.date
        if isinstance(self.value, numbers.Number):
            dct['number'] = self.value
        elif isinstance(self.value, basestring):
            dct['text'] = self.value

        dct['timeseries'] = self.timeseries_id
        dct['doc_id'] = self.doc_id

        return dct


class TimeSeries(object):
    def __init__(self, meta_data):
        self.meta_data = meta_data
        self.doc_id = self.get_doc_id(meta_data)

    def get_doc_id(self, meta_data):
        md_str = json.dumps(meta_data, sort_keys=True, cls=DecimalJSONEncoder)
        hash_object = hashlib.sha1(md_str)
        return hash_object.hexdigest()

    def to_dict(self):
        dct = {}
        dct["metadata"] = self.meta_data
        dct['doc_id'] = self.doc_id
        dct['type'] = "TimeSeries"
        return dct


class ProcessTimeSeries():
    def is_number(self, s):
        try:
            number = float(s)
            return True, number
        except ValueError:
            pass

        try:
            import unicodedata
            number = unicodedata.numeric(s)
            return True, number
        except (TypeError, ValueError):
            pass
        return False, 0

    def impute_values(self, ts, threshold):
        total = 0
        index = 0
        missing_value_index = []
        for element in ts:
            if len(element) <= 2:
                value = element[1]
                if isinstance(value, numbers.Number):
                    total += 1
                elif isinstance(value, basestring):
                    is_n, n_value = self.is_number(value)
                    if is_n:
                        total += 1
                        ts[index] = [element[0], n_value]
                    else:
                        missing_value_index.append(index)
                else:
                    missing_value_index.append(index)

                index += 1

        if total*1.0/len(ts) >= threshold:
            n_missing = len(missing_value_index)
            for i in range(n_missing):
                index = missing_value_index[i]
                print index
                if index == 0:
                    next = 1
                    while next < n_missing and next == missing_value_index[next]:
                        next += 1
                    ts[index] = [ts[index][0], ts[next][1]]
                else:
                    ts[index] = [ts[index][0], ts[index-1][1]]

            return ts

        else:
            return None

    def processs(self, tables):
        result = []
        for sheet in tables:
            for timeseries in sheet:
                ts = TimeSeries(timeseries['metadata'])
                processed_ts = self.impute_values(timeseries['ts'], 0.8)
                if processed_ts is not None:
                    result.append(ts.to_dict())
                    for ts_element in processed_ts:
                        measurement = Measurement(ts.doc_id, ts_element)
                        result.append(measurement.to_dict())
        return result

    def load_json(self, json_fn):
        anfile = open(json_fn)
        json_decoded = demjson.decode(anfile.read(), return_errors=True)
        for msg in json_decoded[1]:
            if msg.severity == "error":
                logging.error(msg.pretty_description())
        return json_decoded[0]

    def write_result_to_file(self, output_fn, output):
        json_output = []
        for item in output:
            json_output.append(json.dumps(item, cls=DecimalJSONEncoder))

        with open(output_fn, "wb") as fp:
            writer = jsonlines.Writer(fp)
            writer.write_all(json_output)



def main():
    test = ProcessTimeSeries()
    tables = test.load_json(sys.argv[1])
    print test.processs(tables)
    test.write_result_to_file(sys.argv[2], test.processs(tables))


if __name__ == "__main__":
    main()