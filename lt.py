import pandas as pd


def csv_to_pwl(df, column, max_val=3):
    """
    Produces as PWL file for LTSPICE from an CSV file recording
    :param max_val:
    :param df: assumes that the frame as a 'Time' column and converts to microseconds
    :param column:
    :return: a string that can be copied into a PWL statement in spice
    """
    f = open(column + '.txt', 'w')

    dn = pd.DataFrame(columns=['Time', column])
    dn['Time'] = round(df[df[column].diff() != 0]['Time'] * 1e6)
    dn[column] = df[df[column].diff() != 0][column]
    dn[column] = (dn[column] != 0) * max_val

    previous_value = None
    cmd_str = None
    for row in dn.itertuples(index=False):
        # print(f'Reference: {list(row)}')
        if row[0] == 0:
            # print(row[0], row[1])
            part_1 = f'{row[0]:.0f}u {row[1]:.0f}'
            cmd_str = 'PWL(' + part_1 + ' '
            f.write(part_1 + '\n')
            previous_value = row[1]
        else:
            part_1 = f'{row[0]:.0f}u {previous_value:.0f}'
            part_2 = f'{row[0] + 1:.0f}u  {row[1]:.0f}'
            cmd_str = cmd_str + part_1 + ' ' + part_2
            f.write(part_1 + '\n')
            f.write(part_2 + '\n')
            # print(row[0], previous_value)
            # print(row[0] + 1, row[1])
            previous_value = row[1]

    f.close()
    return cmd_str + ')'


class PSE:
    """The PSE class reads AC specification from LTSpice Netlist and generates PWL Files.
    """
    def __init__(self, net_list_file):
        self.script = get_script_from_net_list(net_list_file)
        self.rise_time = 1
        self.frame, self.pw, self.dt0, self.rpw, self.dt1, self.gap = build_frame_from_script(self.script)
        make_pwl_files_from_frame(self.frame)
        self.period = (self.pw + self.dt0 + self.rpw + self.dt1)
        self.frequency = 1 if self.period == 0 else int(1e6 / self.period)


def build_frame_from_script(script):
    """
    Takes the script as a list
    :param script:
    Python Script to build PWL Files
        label   dt      dac amp rb1 rb2
        start,  0,      0,  0,  0,  0
        pw,     240,    1,  1,  0,  0
        dt0,    60,     0,  0,  0,  0
        rpw,    480,    1,  0,  0,  0
        dt1,    500,    0,  0,  1,  1
        gap,    10,     0,  0,  0,  0
    :return:
    """
    # Operating in uS
    rise_time = 1
    frame = []
    times = []
    for row in script:
        e_list = row.split(',')
        e_list[0] = 0   # zero out label use for time
        o_list = e_list.copy()
        e_list[1] = rise_time
        e_list = [round(float(j), 1) for j in e_list]
        o_list = [round(float(j), 1) for j in o_list]
        times.append(o_list[1])
        frame.append(e_list)
        frame.append(o_list)
    frame.pop(0)
    accumulated_time = 0
    for index, row in enumerate(frame):
        accumulated_time += row[1]
        row[0] = accumulated_time
    pw = times[1]
    dt0 = times[2]
    rpw = times[3]
    dt1 = times[4]
    gap = times[5]
    return frame, pw, dt0, rpw, dt1, gap


def get_script_from_net_list(net_list_file):
    with open(net_list_file, 'r') as f:
        for line in f:
            if line.find("Python Script") != -1:
                import re
                string = re.sub(' +', ' ', line)
                string = re.sub('\t', ' ', string)
                string = re.sub('\n', ' ', string)
                my_list = string.split(sep='\\n')
                my_list.pop(0)  # loose header
                my_list.pop(0)  # loose labels
    return my_list


def convert_script_to_list(script):
    import re
    script = re.sub(' +', ' ', script)
    script = re.sub('\t', ' ', script)
    script = re.sub('\n', ' ', script)
    script_list = script.split(sep='\\n')
    return script_list


def parse_param_string(string):
    """
    Expects a string with a number and an optional unit
    Strips out number and if a recognized unit is found multiplies number
    :param string: Number and Optional Spice Unit characters
    :return: float in cgs units
    """
    import re
    ss = string.split('=')[1]
    val = float(re.search('[0-9]+', ss).group())
    if ss.lower().find('meg') > 0:
        val *= 1e6
    elif ss.lower().find('k') > 0:
        val *= 1e3
    elif ss.lower().find('m') > 0:
        val *= 1e-3
    elif ss.lower().find('u') > 0:
        val *= 1e-6
    elif ss.lower().find('n') > 0:
        val *= 1e-9
    elif ss.lower().find('p') > 0:
        val *= 1e-12
    return val


def make_pwl_files_from_frame(frame):

    columns = ['Time', 'dt', 'dac_en', 'amp_sel', 'rebal1', 'rebal2']
    dfs = pd.DataFrame(frame, columns=columns)

    for col in columns[2:]:
        spice_make_pwl(dfs, col)


def spice_make_pwl(df, column):
    """
    Produces as PWL file from a frame
    :param df: Must have a 'Time' column and specified addtional column
    :param column: a string that determines the filename and column in df
    """
    dn = pd.DataFrame(columns=['Time', column])
    dn.Time = df.Time.astype(str) + 'u'
    dn[column] = df[column].astype(str)
    dn.to_csv(column + '.txt', sep=' ', header=None, index=None)
    return



def make_ac_pwl_file_for_spice(amplitude_ua=-1000, pulsewidth_us=240, ipi=60, rpr=2, requested_frequency=500, cycles=2):
    """
    Produces as PWL file for LTSPICE from a PSE AC Specification

    :param requested_frequency:
    :param cycles:
    :param ipi:
    :param rpr:
    :param amplitude_ua:
    :param pulsewidth_us:
    :return: a string that can be copied into a PWL statement in spice
    """
    # Amplitude
    columns = ['Time', 'dt', 'dac_en', 'amp_sel', 'rebal1', 'rebal2', 'ie_en', 'cap_byp', 'pw_amp', 'rpw_amp']
    pw_amp = 1e-6 * amplitude_ua
    rpw_amp = 1e-6 * amplitude_ua / rpr

    s = 1
    pw = pulsewidth_us - pulsewidth_us % 15  # Convert to 15uS increment

    rpw = pw * rpr
    dt0 = ipi - (ipi % 15)
    dt1 = (1E6 / requested_frequency) - pw - dt0 - rpw
    dt1 = int(dt1 - (dt1 % 15))
    period = (pw + dt0 + rpw + dt1)
    frequency = 1 if period == 0 else int(1e6 / period)
    print(f'Pulse specs: F:{frequency}Hz PW:{pw} IPI:{dt0} RPW:{rpw} dt1:{dt1}')

    data = [
        #        da am r1 r2
        [0, 0,   0, 0, 0, 0],
        [0, pw,  1, 1, 0, 0],
        [0, dt0, 0, 0, 0, 0],
        [0, rpw, 1, 0, 0, 0],
        [0, dt1, 0, 0, 1, 1]
    ]
    dfs = pd.DataFrame(data, columns=columns)
    dfs['Time'] = dfs['dt'].cumsum()

    dt = 1
    df = pd.DataFrame(columns=columns)

    # time = 0
    for i, row in dfs.iterrows():  # add extra twos to form piecewise file
        df.loc[2 * i] = dfs.loc[i]
        df.loc[2 * i + 1] = dfs.loc[i]
        df['Time'].loc[2 * i + 1] = df['Time'].loc[2 * i + 1] + dt

    df['amp_sel'] = df['amp_sel'].shift(-1)
    df['dac_en'] = df['dac_en'].shift(-1)
    df['rebal1'] = df['rebal1'].shift(-1)
    df['rebal2'] = df['rebal2'].shift(-1)
    df['ie_en'] = df['ie_en'].shift(-1)
    df['cap_byp'] = df['cap_byp'].shift(-1)
    df = df.dropna()

    dn = df.copy()

    for cycle in range(cycles):
        dn.Time = dn.Time + period + 1
        df = df.append(dn)

    for i in range(2, 10):
        spice_make_pwl(df, columns[i])

    return dfs, df, dn
