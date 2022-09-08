import os
import hashlib
import time

# for debugging
from pprint import pprint


class ParserPCF:
    """Parses Hexagon .pcf file to return isometric contents

    Returns several json objects for storage into MongoDB structure"""

    def __init__(self, filename):
        # public attributes for class
        self.filename = filename
        self.md5 = None
        self.lastmod = None
        self.lines = None
        self.check = None
        self.revision = None

        # flagging variables for internal methods
        self.currentline = 0
        self.indent_marker = 0
        self.prev_indent_marker = 0
        # 0=header|1=pipline_id|2=components|3=end-connections|4=materials
        self.section = 0

        # children objects for referencing each part of the pcf file
        self.header = HeaderObj()
        self.pipeline_id = PipelineIDObj()
        self.components = []
        self.endpoints = []
        self.materials = []

        # init file properties by checking file
        self.check = self.check_file()

    def check_file(self):
        """checks to ensure the file type is .pcf, otherwise
        -prints "skipping: [filename], not pcf file..."
        -returns None
        -called by __init__, result stored in self.check"""
        if self.filename.lower().find('.pcf', 0) != -1:
            # read byte file
            self.revision = self.get_rev()
            with open(self.filename, "rb") as f:
                # store md5 of file
                bytes = f.read()
                self.md5 = hashlib.md5(bytes).hexdigest()
                # close the file so that it can be read again
                f.close()
            # read file with UTF-8 encoding
            with open(self.filename) as f:
                # store last modification time
                self.lastmod = time.strftime('%m/%d/%Y %I:%M %p',
                                             time.gmtime(os.path.getmtime(self.filename)))
                # store file lines
                self.lines = f.readlines()
                # close the file gracefully
                f.close()
            return 1

        else:
            print(f"Skipping {self.filename}, not a pcf file...")
            return None

    def read_file(self):
        """reads pcf file, line by line, calling appropriate method
        based on line content"""

        if self.lines == None:
            return
        # begin for loop for entirety of the file
        for line in self.lines:
            # add emergency stop to avoid run-time erros
            if self.currentline > len(self.lines):
                print(
                    f'DEBUG1: Hit emergency stop on \
                    file {self.filename} \
                    line {self.currentline}')
                break

            # store previous line indent_marker
            self.prev_indent_marker = self.indent_marker

            # set new indent_marker based on first character of current line
            if self.lines[self.currentline][0].isspace():
                self.indent_marker = 1

            else:
                self.indent_marker = 0

            keyword = self.determine_line()
            # check what previous indent status was

            # Case where prev line was UNINDENTED and current line is UNINDENTED
            if self.prev_indent_marker == 0 and self.indent_marker == 0:
                # print(f"({self.currentline+1})todo-un/un")
                if keyword == 'HEADER':
                    # process as header item
                    # print(f'DEBUG: keword was HEADER')
                    self.process_header()

                elif keyword == 'PIPELINE-REFERENCE':
                    # process as materials list begin
                    # print(f'DUBUG: keyword was PIPELINE-REFERENCE')
                    # set section to pipeline_id
                    self.section = 1
                    # process first tag of the pipeline id section
                    self.process_pipeline_id()

                elif keyword == 'MATERIAL-ITEM':
                    self.materials.append(MaterialObj())

                    # process name of material while still on opening line
                    tag, value = self.read_tag()
                    setattr(self.materials[-1], tag, value)

                else:
                    print(f'DEBUG2: unknown condition at \
                        line: {self.currentline+1} \
                        in {self.filename}, \
                        keyword: {keyword}, \
                        prev_indent_marker: {prev_indent_marker}, \
                        indent_marker: {indent_marker}')

            # Case where prev line was UNINDENTED and current line is INDENTED
            elif self.prev_indent_marker == 0 and self.indent_marker == 1:
                # print(f"({self.currentline+1})todo-un/in")
                # if case where header is indented
                if self.section == 0:
                    print(f'DEBUG3: unknown case of indent \
                        in header line {self.currentline}')

                # if case where in pipeline id section
                elif self.section == 1:
                    self.process_pipeline_id()

                # if case where in components section
                elif self.section == 2:
                    # process first component
                    self.process_component()

                # if case where in endpoints section
                elif self.section == 3:
                    # process endpoint attribute
                    self.process_end_position()

                # if case where in materials section
                elif self.section == 4:
                    self.process_material()

            # Case where prev line was INDENTED and current line is UNINDENTED
            elif self.prev_indent_marker == 1 and self.indent_marker == 0:
                if keyword == 'COMPONENT':
                    # set section to components
                    self.section = 2
                    # create new component object into list
                    self.components.append(ComponentObj())
                    # process type of component while still on opening line
                    tag, value = self.read_tag()
                    setattr(self.components[-1], 'component_type', tag.upper())

                elif keyword == 'END-POINT':
                    # set section to end-connections
                    self.section = 3
                    self.endpoints.append(EndPositionObj())
                    # process type of endpoint while still on opening line
                    tag, value = self.read_tag()
                    setattr(self.endpoints[-1], 'endpoint_type', tag.upper())

                elif keyword == 'MATERIALS-LIST-BEGIN':
                    # process as materials list begin
                    self.section = 4

                elif keyword == 'MATERIAL-ITEM':
                    # set section to end-connections
                    self.materials.append(MaterialObj())
                    # process type of material while still on opening line
                    tag, value = self.read_tag()
                    setattr(self.materials[-1], tag, value)

            # Case where prev line was INDENTED and current line is INDENTED
            elif self.prev_indent_marker == 1 and self.indent_marker == 1:
                if self.section == 1:
                    self.process_pipeline_id()

                # if case where in components section
                elif self.section == 2:
                    # process component attribute
                    self.process_component()

                elif self.section == 3:
                    # process endpoint attribute
                    self.process_end_position()

                elif section == 4:
                    self.process_material()

                else:
                    pass

            else:
                print(f'DEBUG4: unknown condition: \
                    prev_indent_marker = {self.prev_indent_marker} \
                    and indent_marker = {self.indent_marker} \
                    in {self.filename} at line {self.currentline}')

            self.currentline += 1

    def determine_line(self, line=None):
        if line == None:
            line = self.currentline

        header_words = [
            'ISOGEN-FILES',
            'UNITS-BORE',
            'UNITS-CO-ORDS',
            'UNITS-BOLT-LENGTH',
            'UNITS-BOLT-DIA',
            'UNITS-WEIGHT'
        ]
        component_words = [
            'FLANGE',
            'WELD',
            'FLANGE-BLIND',
            'GASKET',
            'BOLT',
            'ELBOW',
            'PIPE',
            'SUPPORT',
            'COUPLING',
            'TEE',
            'MISC-COMPONENT',
            'VALVE',
            'PIPE-FIXED',
            'REDUCER-CONCENTRIC',
            'OLET',
            'CAP',
            'ADDITIONAL-ITEM',
            'LOCATION-POINT',
            'INSTRUMENT',
            'INSTRUMENT-ANGLE',
            'FLANGE-REDUCING-CONCENTRIC',
            'UNION',
            'FLOW-ARROW'
        ]
        if any(word in self.lines[line].upper() for word in header_words):
            return 'HEADER'

        elif self.lines[line].upper().find('PIPELINE-REFERENCE', 0) != -1:
            return 'PIPELINE-REFERENCE'

        elif self.lines[line][0:3].upper().find('END', 0) != -1:
            return 'END-POINT'

        elif self.lines[line].upper().find('MATERIALS', 0) != -1:
            return 'MATERIALS-LIST-BEGIN'

        elif self.lines[line][0:10].upper().find('ITEM', 0) != -1:
            return 'MATERIAL-ITEM'

        elif any(word in self.lines[line].upper() for word in component_words):
            return 'COMPONENT'

        elif self.lines[line][0].isspace:
            return 'BLANK'

        else:
            print(f'DEBUG5: Unknown keyword in {self.filename} \
                at line {line}: {self.lines[line]}')

    def process_header(self):
        """processes pcf file header"""
        tag, value = self.read_tag()
        setattr(self.header, tag, value)

    def process_pipeline_id(self):
        """processes pipeline reference section"""
        tag, value = self.read_tag()
        setattr(self.pipeline_id, tag, value)

    def process_component(self):
        """processes typical component as defined in reference docs"""
        tag, value = self.read_tag()

        # add logic to rename endpoint connections so both can be stored
        if tag == 'end_point':
            if hasattr(self.components[-1], 'end_point1'):
                tag = 'end_point2'
            else:
                tag = 'end_point1'

        setattr(self.components[-1], tag, value)

    def process_end_position(self):
        """processes a single end position"""
        tag, value = self.read_tag()
        setattr(self.endpoints[-1], tag, value)

    def process_material(self):
        """processes a single material in material list"""
        tag, value = self.read_tag()
        setattr(self.materials[-1], tag, value)

    def read_tag(self, line=None):
        """processes a line, returns tag and property as a tuple"""
        if line == None:
            line = self.currentline

        # check if requested line is indented or not and set start point
        if self.lines[line][0].isspace():
            search_start = 4
        else:
            search_start = 0

        # set end point as next space found in string
        search_end = self.lines[line].find(" ", search_start)

        # save first word as the tag
        tag = self.lines[line][search_start:search_end].lower(
        ).replace("-", "_")

        # reset search parameters to look for value
        search_start = search_end

        # search for next non-space character
        i = 0
        for char in self.lines[line][search_start:]:
            if char.isspace():
                i += 1
            else:
                search_end = search_start + i
                break

        # Pull value and strip end characters, replace $ with a space
        value = self.lines[line][search_end:].rstrip().replace("$", " ")

        # return the result
        return (tag, value)

    def get_rev(self):
        """gets revision of pcf number from filename, because header tag is not accurate"""
        return self.filename[-6:-4]

class HeaderObj:
    """Creates empty object contianing info for
    header section from pcf file"""
    None


class PipelineIDObj:
    """Creates empty object containing info for
    pipeline id section from pcf file"""
    None


class ComponentObj:
    """Creates empty object containing info for
    single component from pcf file"""
    None


class EndPositionObj:
    """Creates empty object containing info for
    single end point connection from pcf file"""
    None


class MaterialObj:
    """Creates empty object containing info for
    material in materials section from pcf file"""
    None

# DUBUGGING AREA


CWD = 'C:\\Users\\me\\OneDrive - NARL Refining LP\\Ryan Isos'
os.chdir(CWD)

# sets dirs as a list object of each file name (file names saved as strings)
dirs = os.listdir()
pcf = ParserPCF(dirs[0])
# for file in dirs:
#   print(dirs.index(file))
# if pcf.md5:
#   print(pcf.filename)
#   print(pcf.md5)
#   print(pcf.lastmod)
#   print(pcf.lines)

# Full Loop
for file in range(0, len(dirs)):
    # print(f'File Number: {file}')
    pcf = ParserPCF(dirs[file])
    if pcf.check:
        # print(pcf.filename)
        # print(pcf.md5)
        # print(pcf.lastmod)
        # print(pcf.revision)
        pcf.read_file()
        # pprint(vars(pcf.header))
        # pprint(vars(pcf.pipeline_id))
        for i in range(0, len(pcf.components)):
            # print(pcf.components[i].component_type)
            pprint(vars(pcf.components[i]), width=200)

        # for i in range(0, len(pcf.endpoints)):
        #     print(pcf.endpoints[i].endpoint_type)
        #     pprint(vars(pcf.endpoints[i]), width=100)

        # print('Materials:')
        # for i in range(0, len(pcf.materials)):
        #     # print(pcf.materials[i].endpoint_type)
        #     print(f'item_code: {pcf.materials[i].item_code}')
        #     print(f'\t description: {pcf.materials[i].description}')
        #     # print(f'\t {vars(pcf.materials[i])}')
    else:
        pass

# single file
# file = 1328
# print(pcf.filename)
# print(pcf.md5)
# print(pcf.lastmod)
# pcf = ParserPCF(dirs[file])
# pcf.read_file()
# pprint(vars(pcf.header))
# pprint(vars(pcf.pipeline_id))
# for i in range(0,len(pcf.components)):
#     print(pcf.components[i].component_type)
#     pprint(vars(pcf.components[i]), width=100)

# for i in range(0,len(pcf.endpoints)):
#     print(pcf.endpoints[i].endpoint_type)
#     pprint(vars(pcf.endpoints[i]), width=100)

# print('Materials:')
# for i in range(0,len(pcf.materials)):
#     # print(pcf.materials[i].endpoint_type)
#     print(f'item_code: {pcf.materials[i].item_code}')
#     print(f'\t description: {pcf.materials[i].description}')
#     # print(f'\t {vars(pcf.materials[i])}')
