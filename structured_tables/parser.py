# Copyright (c) 2016 Civic Knowledge. This file is licensed under the terms of the
# Revised BSD License, included in this distribution as LICENSE

"""
Parser for the Simple Data Package format.
"""

NO_TERM = '<no_term>'  # No parent term -- no '.' --  in term cell
ELIDED_TERM = '<elided_term>'  # A '.' in term cell, but no term before it.


class Term(object):
    """Parses a row into the parts of a term"""

    def __init__(self, term, value, term_args, is_arg_child=False):

        self.parent_term = None
        self.record_term = None
        self.value = None
        self.term_value_name = '@value'  # May be change in term parsing
        self.args = None

        if '.' in term:
            self.parent_term, self.record_term = term.split('.')
            self.parent_term, self.record_term = self.parent_term.strip(), self.record_term.strip()

            if self.parent_term == '':
                self.parent_term = ELIDED_TERM

        else:
            self.parent_term, self.record_term = NO_TERM, term.strip()

        self.value = value.strip()

        self.args = [x.strip() for x in term_args]

        self.is_arg_child = is_arg_child

    def child_terms(self, param_map):
        """Given a parameter map, iterate over the child terms"""

        for term, value in zip(param_map, self.args):
            if term.strip() and value.strip():
                yield Term(self.record_term + '.' + term, value, [], is_arg_child=True)

    def __repr__(self):
        return "<Term: {}.{} {} {} >".format(self.parent_term, self.record_term, self.value, self.args)

    def __str__(self):
        if self.parent_term == NO_TERM:
            return "{}: {}".format(self.record_term, self.value)

        elif self.parent_term == ELIDED_TERM:
            return ".{}: {}".format(self.record_term, self.value)

        else:
            return "{}.{}: {}".format(self.parent_term, self.record_term, self.value)


class TermParser(object):
    """Generate terms from a row generator. It will produce a term for each row, and child
    terms for any arguments to the row. """

    def __init__(self, row_gen, root_directory=None):
        """

        :param row_gen: an interator that generates rows
        :return:
        """

        self._row_gen = row_gen
        self._param_map = []

        self._synonyms = {}
        self._value_names = {}

        self._root_directory = root_directory

        self.errors = []

    def _handle_term(self, term, value, term_args):
        pass

    def _include_file(self, value):

        import csv

        if value.startswith('http'):
            import urllib2
            f = urllib2.urlopen(value)
        else:
            from os.path import join

            f = open(join(self._root_directory, value.strip('/')))

        return f

    def __iter__(self):
        """An interator that generates term objects"""

        for row in self._row_gen:

            if not row[0].strip():
                continue

            # Substitute synonyms
            try:
                row[0] = self._synonyms[row[0].lower()]

            except KeyError:
                pass

            t = Term(row[0].lower(), row[1], row[2:])

            # Remapping the default record value to another property name

            if t.record_term.lower() == 'termvaluename':
                self._value_names[t.value.lower()] = t.args[0]
                continue
            else:
                t.term_value_name = self._value_names.get(t.record_term.lower(), '@value')

            # Section and Term terms update the parameter map
            if t.record_term.lower() in ('section', 'term'):
                self._param_map = t.args
                continue

            # Synonym terms change the term names
            if t.record_term.lower() == 'synonym':
                try:
                    self._synonyms[t.value.lower()] = t.args[0].lower()
                except IndexError as e:
                    self.errors.append((t, e.message))

                continue

            if t.record_term.lower() == 'include':
                import csv
                from os.path import dirname

                f = self._include_file(t.value)

                for t in TermParser(csv.reader(f), dirname(f.name)):
                    yield t

                f.close()
                continue

            yield t

            for c in t.child_terms(self._param_map):
                yield c


class Record(object):
    """Parses a row into the parts of a term"""

    def __init__(self, term, value, children=None, term_value_name=None):

        self.term = term.strip()
        self.value = value
        self.term_value_name = '@value' if not term_value_name else term_value_name
        self.children = [] if not children else children

    def add_child(self, child):

        self.children.append(child)

    def __contains__(self, item):

        if isinstance(item, Record):
            raise NotImplementedError
        else:
            for c in self.children:
                if item == c.term:
                    return True

            else:
                return False

    def __getitem__(self, item):

        records = []

        for c in self.children:
            for c in self.children:
                if item == c.term:
                    records.append(c)

        return records

    def __repr__(self):
        return "<record: {}: {} = {}  >".format(self.term, self.term_value_name, self.value, )


def generate_records(term_generator):
    """Return a heirarchy of records from a stream of terms

    :param term_generator:
    """

    root = Record('Root', None)
    last_term_map = {NO_TERM: root}

    for term in term_generator:

        record = Record(term.record_term, term.value, term_value_name=term.term_value_name)

        parent = last_term_map[term.parent_term.lower()]
        parent.add_child(record)

        if not term.is_arg_child and term.parent_term != ELIDED_TERM:
            # Recs created from term args don't go in the maps.
            # Nor do record term records with elided parent terms
            last_term_map[ELIDED_TERM] = record
            last_term_map[term.record_term.lower()] = record

    return root


def dump_records(r, level=0):
    print ('  ' * level) + str(r)

    for c in r.children:
        dump_records(c, level + 1)


def convert_to_dict(record):
    """Converts a record heirarchy to nested dicts.

    :param record:

    """

    if record.children:

        d = {}

        for c in record.children:
            try:
                d[c.term].append(convert_to_dict(c))
            except KeyError:
                # The c.term property doesn't exist, so add a scalar
                d[c.term] = convert_to_dict(c)
            except AttributeError:
                # d[c.term] exists, but is a scalar, so convert it to a list
                d[c.term] = [d[c.term]] + [convert_to_dict(c)]

        if record.value:
            d[record.term_value_name] = record.value

        return d

    else:
        return record.value
