import argparse
import sys
import os
import re
import importlib
import shutil
import pandas as pd
from collections import Counter
from pathlib import Path

import csv
#import statistics
#import math
#import xlsxwriter
#import json
#from xlsxwriter.utility import xl_rowcol_to_cell
#from xlsxwriter.utility import xl_range




def string2floatList(input_str):
  return list(map(float, input_str.split(';')))

def status(x):
  return pd.Series([
    x.count(), x.min(),x.idxmin(), x.quantile(.25), x.median(), 
    x.quantile(.75), x.mean(), x.max(), x.idxmax(), 
    x.var(), x.std(), x.skew(), x.kurt()], 
    index=['COUNT','MIN', 'IDX_MIN','25%','50%', '75%',
          'MEAN', 'MAX', 'IDX_MAX','VAR', 'STD', 'SKEW', 'KURT'])

def build_parser():
  parser = argparse.ArgumentParser()
  subcmd = parser.add_subparsers(
    required=True,
    dest='subcmd',
    help='sub commands')

  anz_parser = subcmd.add_parser('summary', help='XXXX')
  anz_parser.add_argument('-o', '--output', 
      help='please input the output folder', dest='output', required=True)
  anz_parser.add_argument('-i', '--input', 
      help='please input the input folder', dest='input', required=True)
  return parser


def parsing_Results(db, line):
  pattern = (r'Segment\s*(\d*)\s*\[(.*)\];(.*);(.*)')
  regex = re.compile(pattern)

  match = regex.finditer(line)
  for m in match:
    #print(m.groups())
    segment = m.group(1)
    db[segment] = {'attr':m.group(2), 'val':m.group(3), 'unit':m.group(4)}
    pass
  return

def parsing_Global(db, line):
  pattern = (r'(.*);(.*);(.*)')
  regex = re.compile(pattern)

  match = regex.finditer(line)
  for m in match:
    attr = m.group(1)
    db[attr] = {'val':m.group(2), 'unit':m.group(3)}

    if m.group(2) == '--.--':
      print (f'\t{line}')    
      #db[attr]['val'] = '99999999'
    pass
  return

def parsing_Curves(db, line):
  if 'Time' in line:
    pattern = (r'Time\s*\[(.*)\];(.*);')
    regex = re.compile(pattern)
    match = regex.finditer(line)

    for m in match:
      interval = m.group(1)
      data_float = string2floatList(m.group(2))
      db.setdefault('Time', data_float)
      db.setdefault('interval', interval)
      pass

  elif 'Segment' in line:
    pattern = (r'Segment\s*(\d*);(.*);')
    regex = re.compile(pattern)
    match = regex.finditer(line)

    for m in match:
      id = m.group(1)
      data_float = string2floatList(m.group(2))
      segment_db = db.setdefault('Segment', {})
      segment_db[id] = data_float
      pass
  else:
    pattern = (r'(.*?);(.*);')
    regex = re.compile(pattern)
    match = regex.finditer(line)

    for m in match:
      attr = m.group(1)
      data_float = string2floatList(m.group(2))
      db.setdefault(attr, data_float)
      pass
  return

def process_one_file(file_path, error_log):
  print(f'processing file_path:{file_path}...')
  if not file_path.exists():
    with open(error_log, 'a') as f:
      errmsg = f'NO EXIST!! {file_path}'
      print(errmsg)
      f.write(errmsg+'\n')
    return {}

  lines = None
  with open(file_path, 'r') as f:
    lines = f.readlines()

  section = 0
  sub_section = 0
  label_percentage  = {'Global Strain A2C',
                      'Global Strain A3C',
                      'Global Strain A4C',
                      'Longitudinal Strain'}
  label_rate        = {'Global Strain Rate A2C',
                      'Global Strain Rate A3C',
                      'Global Strain Rate A4C',
                      'Longitudinal Strain Rate'}

  #label_all = label_percentage | label_rate

  infos = {'Global':{}, 'Results':{}, 'Curves':{}}
  uint_type = None
  for line in lines:
    line = line.strip()
    #print(line)
    if 'Global' == line:
      section = 1
    elif 'T2P' in line:
      section = 2
    elif 'End-systolic' in line:
      section = 3
    elif 'Peak-systolic' in line:
      section = 4
    elif 'Curves' in line:
      section = 5
      sub_section = None
      unit_type = None
    else:
      pass

    if section == 1:
      db = infos['Global']
      parsing_Global(db, line)
    elif section == 2:
      db = infos['Results'].setdefault('T2P', {})
      parsing_Results(db, line)
    elif section == 3:
      db = infos['Results'].setdefault('End-systolic', {})
      parsing_Results(db, line)
    elif section == 4:
      db = infos['Results'].setdefault('Peak-systolic', {})
      parsing_Results(db, line)
    elif section == 5:
      db = None
      if line in label_percentage:
        unit_type = '%'
        sub_section = line
      elif line in label_rate:
        unit_type = '1/s'
        sub_section = line
      else:
        pass

      # print(f'section:{section}, {sub_section}, {uint_type}, line:{line}')
      if unit_type is not None:
        db_section = infos['Curves'].setdefault(sub_section, {})
        parsing_Curves(db_section, line)
    else:
      pass
  
  '''
  print(infos['Global'])
  info = infos['Curves']
  for section, db_section in info.items():
    print(f'{section}, keys:{db_section.keys()}')
    for key, val in db_section.items():
      print(f'\t\tkey:{key}, val:{val}')
    print('*'*40)
  '''
  return infos

def process_one_case(input_path, case_id, error_log):
  def get_file_path(input_path, case_id, file_type):
    return input_path.joinpath(f'QLAB_{case_id}', f'{file_type}{case_id}.txt')

  file_path = get_file_path(input_path, case_id, 'LA')
  db_LA = process_one_file(file_path, error_log)

  file_path = get_file_path(input_path, case_id, 'LV')
  db_LV = process_one_file(file_path, error_log)

  file_path = get_file_path(input_path, case_id, 'RV')
  db_RV = process_one_file(file_path, error_log)
  
  return {'LA':db_LA, 'LV':db_LV, 'RV':db_RV}

def data_process(one_case_db):
  # #Global, Results, Curves
  files = ['LA', 'LV', 'RV']
  
  dbs_global = [one_case_db[files[0]]['Global'],
                one_case_db[files[1]]['Global'],
                one_case_db[files[2]]['Global']]

  dbs_res = [one_case_db[files[0]]['Results'],
             one_case_db[files[1]]['Results'],
             one_case_db[files[2]]['Results']]

  attrs = {}
  for file_type, db in zip(files, dbs_global):
    #print(db.items())
    for key, data in db.items():
      val = data['val']
      unit = data['unit']
      idx_key = f'{file_type}_{key}({unit})'
      attrs[idx_key] = val
      # print(idx_key,  data)
    pass

  for file_type, db in zip(files, dbs_res):
    #print(db.items())
    for key, segments in db.items():
      for seg_id, data in segments.items():
        attr = data['attr']
        val = data['val']
        unit = data['unit']
        idx_key = f'{file_type}_{key}_{attr}({unit})'
        attrs[idx_key] = val
        #print(idx_key,  val)
    pass
  return attrs

def data_process_curves(output_path, case_list, cases_db_list):
  print('###############################')
  print('# process curves')
  print('###############################')

  files = ['LA', 'LV', 'RV']
  curves_all_section_db = {}
  output_list = []

  for case_id, one_case_db in zip(case_list, cases_db_list):
    print(f'{case_id}')
    dbs_curves = [
                one_case_db[files[0]]['Curves'],
                one_case_db[files[1]]['Curves'],
                one_case_db[files[2]]['Curves']]

    #print(dbs_curves)
    for file_type, db in zip(files, dbs_curves):
      #print(db.keys())
      for section, attrs in db.items():
        file_section_name = f'{file_type}_{section}'
        #print(file_section_name)
        for key, data in attrs.items():
          if 'interval' == key:
            continue
          if 'Segment' in key:
            segmentData = data
            for seg_id, a_list_of_data in data.items():
              output_list.append( [case_id, file_type, section, f'Segment_{seg_id}'] + a_list_of_data)
          else:
            a_list_of_data = data
            output_list.append( [case_id, file_type, section, key] + a_list_of_data)

            file_section_key_name = f'Curves_{file_section_name}_{key}'
            #print(f'\tkey:{file_section_key_name}')
            #print(f'\t\tdata:{a_list_of_data}')
            #section_db = curves_all_section_db.setdefault(file_section_key_name, {})
            #section_db[case_id] = a_list_of_data
    pass

  output_file_path = output_path.joinpath(f'curves.csv')
  with open(output_file_path, 'w', newline='') as file:
    #writer = csv.writer(file, quoting=csv.QUOTE_ALL,delimiter=';')
    writer = csv.writer(file,delimiter=';')
    writer.writerows(output_list)
  return


def data_process_general(output_path, case_list, cases_db_list):
  print('###############################')
  print('# process General')
  print('###############################')

  output_dict = {}
  for case_id, one_case_db in zip(case_list, cases_db_list):
    print(f'{case_id}')
    one_case_processed_done = data_process(one_case_db)
    output_dict[case_id] = one_case_processed_done
    #print(one_attrs)

  
  df = pd.DataFrame.from_dict(output_dict).T
  #df = df.apply(pd.to_numeric, errors='raise')  
  #df_stats = pd.DataFrame(status(df))
  #print(df)

  output_file_path = output_path.joinpath(f'summary.csv')
  df.to_csv(output_file_path)

  #output_file_path = output_path.joinpath(f'stats.csv')
  #df_stats.to_csv(output_file_path)
  return

def init(args):
#  cur_path = Path(__file__).parent.resolve()
  input_path = Path(args.input)
  output_path = Path(args.output)



  #os.removedirs(output_path)
  shutil.rmtree(output_path, ignore_errors=True)
  if not os.path.exists(output_path):
    os.makedirs(output_path)

  dirs = os.listdir(input_path)
  case_list = []
  pattern = (r'QLAB_(\d*)$')
  regex = re.compile(pattern)
  for dir in dirs:
    match = regex.finditer(dir)
    for m in match:
      case_list.append(m.group(1))
    pass
  
  return case_list



def main():
  parser = build_parser()
  args = parser.parse_args()

  if args.subcmd == 'summary':
    input_path = Path(args.input)
    output_path = Path(args.output)
    case_list = init(args)

    error_log = output_path.joinpath('error.log')

    print(case_list)

    #case_list = ['0002','0005','0007']
    cases_db_list = []
    for case_id in case_list:
      one_case_db = process_one_case(input_path, case_id, error_log)
      cases_db_list.append(one_case_db)
      pass

    data_process_general(output_path, case_list, cases_db_list)
    
    #output_path_curves = output_path.joinpath('Curves')
    #if not os.path.exists(output_path_curves):
    #  os.makedirs(output_path_curves)    
    data_process_curves(output_path, case_list, cases_db_list)
    
    return

  return

if __name__ == '__main__':
  main()
  sys.exit(0)
