import os
import yaml
import sys
import argparse
import numpy
import scipy.interpolate
#import collections


class RefractiveIndex:
    """Class that parses the refractiveindex.info YAML database"""

    def __init__(self, databasePath=os.path.join(os.path.dirname(os.path.realpath(__file__)), os.path.normpath("../RefractiveIndex/"))):
        self.referencePath = os.path.normpath(databasePath)
        f = open(os.path.join(self.referencePath, os.path.normpath("catalog.yml")), "r")
        # print(f)
        self.catalog = yaml.safe_load(f)
        f.close()

        # TODO: Do i NEED namedtuples, or am i just wasting time?
        # Shelf = collections.namedtuple('Shelf', ['SHELF', 'name', 'books'])
        # Book = collections.namedtuple('Book', ['BOOK', 'name', 'pages'])
        # Page = collections.namedtuple('Page', ['PAGE', 'name', 'path'])

        # self.catalog = [Shelf(**shelf) for shelf in rawCatalog]
        # for shelf in self.catalog:
        #     books = []
        #     for book in shelf.books:
        #         rawBook = book
        #         if not 'divider' in rawBook:
        #             books.append(Book(**rawBook))
        #         pages = []
        #         for page in book.pages:
        #             rawPage = page
        #             pages.append(Page(**rawPage))
        #         book.pages = pages

    def getMaterialFilename(self, shelf, book, page):
        filename = ''
        # FIXME:There MUST be a way to access an elements w/o iterating over the whole damn dictionary.
        for sh in self.catalog:
            if sh['SHELF'] == shelf:
                for b in sh['books']:
                    if not 'divider' in b:
                        if b['BOOK'] == book:
                            for p in b['pages']:
                                if p['PAGE'] == page:
                                    # print("From {0} opening {1}, {2}\n".format(sh['name'], b['name'], p['name']))
                                    filename =os.path.join(self.referencePath, os.path.normpath(p['path']))
                                    # print("Located at {}".format(filename))
        assert filename != ''
        return filename
    def getMaterial(self, shelf, book, page):
        return Material(self.getMaterialFilename(shelf, book, page))


class Material:
    """ Material class"""

    def __init__(self, filename):
        self.refractiveIndex = None
        self.extinctionCoefficient = None

        f = open(filename)
        material = yaml.safe_load(f)
        f.close()

        for data in material['DATA']:
            if (data['type'].split())[0] == 'tabulated':
                rows = data['data'].split('\n')
                splitrows = [c.split() for c in rows]
                wavelengths = []
                n = []
                k = []
                for s in splitrows:
                    if len(s) > 0:
                        wavelengths.append(float(s[0]))
                        n.append(float(s[1]))
                        if len(s) > 2:
                            k.append(float(s[2]))

                if (data['type'].split())[1] == 'n':

                    if self.refractiveIndex is not None:
                        Exception('Bad Material YAML File')

                    self.refractiveIndex = RefractiveIndexData.setupRefractiveIndex(formula=-1,
                                                                                    wavelengths=wavelengths,
                                                                                    values=n)
                elif (data['type'].split())[1] == 'k':

                    self.extinctionCoefficient = ExtinctionCoefficientData.setupExtinctionCoefficient(wavelengths, n)

                elif (data['type'].split())[1] == 'nk':

                    if self.refractiveIndex is not None:
                        Exception('Bad Material YAML File')

                    self.refractiveIndex = RefractiveIndexData.setupRefractiveIndex(formula=-1,
                                                                                    wavelengths=wavelengths,
                                                                                    values=n)
                    self.extinctionCoefficient = ExtinctionCoefficientData.setupExtinctionCoefficient(wavelengths, k)
            elif (data['type'].split())[0] == 'formula':

                if self.refractiveIndex is not None:
                    Exception('Bad Material YAML File')

                formula = int((data['type'].split())[1])
                coefficents = [float(s) for s in data['coefficients'].split()]
                rangeMin = float(data['range'].split()[0])
                rangeMax = float(data['range'].split()[1])

                self.refractiveIndex = RefractiveIndexData.setupRefractiveIndex(formula=formula,
                                                                                rangeMin=rangeMin,
                                                                                rangeMax=rangeMax,
                                                                                coefficients=coefficents)

    def getRefractiveIndex(self, wavelength):
        if self.refractiveIndex is None:
            raise Exception('No refractive index specified for this material')
        else:
            return self.refractiveIndex.getRefractiveIndex(wavelength)

    def getExtinctionCoefficient(self, wavelength):
        if self.extinctionCoefficient is None:
            raise NoExtinctionCoefficient('No extinction coefficient specified for this material')
        else:
            return self.extinctionCoefficient.getExtinctionCoefficient(wavelength)

#
# Refractive Index
#
class RefractiveIndexData:
    """Abstract RefractiveIndex class"""

    @staticmethod
    def setupRefractiveIndex(formula, **kwargs):
        if formula >= 0:
            return FormulaRefractiveIndexData(formula, **kwargs)
        elif formula == -1:
            return TabulatedRefractiveIndexData(**kwargs)
        else:
            raise Exception('Bad RefractiveIndex data type')

    def getRefractiveIndex(self, wavelength):
        raise NotImplementedError('Different for functionally and experimentally defined materials')


class FormulaRefractiveIndexData:
    """Formula RefractiveIndex class"""

    def __init__(self, formula, rangeMin, rangeMax, coefficients):
        self.formula = formula
        self.rangeMin = rangeMin
        self.rangeMax = rangeMax
        self.coefficients = coefficients

    def getRefractiveIndex(self, wavelength):
        wavelength /= 1000.0
        if self.rangeMin <= wavelength <= self.rangeMax:
            type = self.formula
            coefficients = self.coefficients
            n = 0
            if type == 1:  # Sellmeier
                nsq = 1 + coefficients[0]
                g = lambda c1, c2, w: c1*(w**2)/(w**2 - c2**2)
                for i in range(1, len(coefficients), 2):
                    nsq += g(coefficients[i], coefficients[i + 1], wavelength)
                n = numpy.sqrt(nsq)
            elif type == 2:  # Sellmeier-2
                nsq = 1 + coefficients[0]
                g = lambda c1, c2, w: c1*(w**2)/(w**2 - c2)
                for i in range(1, len(coefficients), 2):
                    nsq += g(coefficients[i], coefficients[i + 1], wavelength)
                n = numpy.sqrt(nsq)
            elif type == 3:  # Polynomal
                g = lambda c1, c2, w: c1*w**c2
                nsq = coefficients[0]
                for i in range(1, len(coefficients), 2):
                    nsq += g(coefficients[i], coefficients[i + 1], wavelength)
                n = numpy.sqrt(nsq)
            elif type == 4:  # RefractiveIndex.INFO
                raise FormulaNotImplemented('RefractiveIndex.INFO formula not yet implemented')
            elif type == 5:  # Cauchy
                g = lambda c1, c2, w: c1*w**c2
                n = coefficients[0]
                for i in range(1, len(coefficients), 2):
                    n += g(coefficients[i], coefficients[i + 1], wavelength)
            elif type == 6:  # Gasses
                n = 1 + coefficients[0]
                g = lambda c1, c2, w: c1/(c2 - w**(-2))
                for i in range(1, len(coefficients), 2):
                    n += g(coefficients[i], coefficients[i + 1], wavelength)
            elif type == 7:  # Herzberger
                raise FormulaNotImplemented('Herzberger formula not yet implemented')
            elif type == 8:  # Retro
                raise FormulaNotImplemented('Retro formula not yet implemented')
            elif type == 9:  # Exotic
                raise FormulaNotImplemented('Exotic formula not yet implemented')
            else:
                raise Exception('Bad formula type')

            return n
        else:
            raise Exception('Wavelength {} is out of bounds. Correct range(um): ({}, {})'.format(wavelength, self.rangeMin, self.rangeMax))


class TabulatedRefractiveIndexData:
    """Tabulated RefractiveIndex class"""

    def __init__(self, wavelengths, values):
        self.rangeMin = numpy.min(wavelengths)
        self.rangeMax = numpy.max(wavelengths)

        if self.rangeMin == self.rangeMax:
            self.refractiveFunction = values[0]
        else:
            self.refractiveFunction = scipy.interpolate.interp1d(wavelengths, values)

    def getRefractiveIndex(self, wavelength):
        wavelength /= 1000.0
        if self.rangeMin == self.rangeMax and self.rangeMin == wavelength:
            return self.refractiveFunction
        elif self.rangeMin <= wavelength <= self.rangeMax and self.rangeMin != self.rangeMax:
            return self.refractiveFunction(wavelength)
        else:
            raise Exception('Wavelength {} is out of bounds. Correct range(um): ({}, {})'.format(wavelength, self.rangeMin, self.rangeMax))

#
# Extinction Coefficient
#
class ExtinctionCoefficientData:
    """ExtinctionCofficient class"""

    @staticmethod
    def setupExtinctionCoefficient(wavelengths, values):
        return ExtinctionCoefficientData(wavelengths, values)

    def __init__(self, wavelengths, coefficients):
        self.extCoeffFunction = scipy.interpolate.interp1d(wavelengths, coefficients)
        self.rangeMin = numpy.min(wavelengths)
        self.rangeMax = numpy.max(wavelengths)

    def getExtinctionCoefficient(self, wavelength):
        wavelength /= 1000.0
        if self.rangeMin <= wavelength <= self.rangeMax:
            return self.extCoeffFunction(wavelength)
        else:
            raise Exception('Wavelength {} is out of bounds. Correct range(um): ({}, {})'.format(wavelength, self.rangeMin, self.rangeMax))


#
# Custom Exceptions
#
class FormulaNotImplemented(Exception):
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)


class NoExtinctionCoefficient(Exception):
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)


# class WavelengthOutOfBounds(Exception):
#     def __init__(self, value):
#         self.value = value
#     def __str__(self):
#         return repr(self.value)


# Stuff to link to matlab
# FIXME: This sucks. Seriously. For one data point we have to open two files, and read the whole catalog.
# EVERY FRIKIN' TIME
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Returns refractive index of material for specified wavelength")
    parser.add_argument('catalog')
    parser.add_argument('section')
    parser.add_argument('book')
    parser.add_argument('page')
    parser.add_argument('wavelength')

    args = parser.parse_args()
    catalog = RefractiveIndex(args.catalog)
    mat = catalog.getMaterial(args.section, args.book, args.page)
    sys.stdout.write(str(mat.getRefractiveIndex(float(args.wavelength))))