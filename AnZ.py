import sys
import os
import re
import importlib
import shutil
import pandas as pd
from collections import Counter
from pathlib import Path

#import math
#import xlsxwriter
#import json
#from xlsxwriter.utility import xl_rowcol_to_cell
#from xlsxwriter.utility import xl_range

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
    pass
  return

def string2floatList(input_str):
  return list(map(float, input_str.split(';')))

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

def process_one_file(file_path):
  print(f'file_path:{file_path}')
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

def process_one_case(case_id):
  def get_file_path(case_id, file_type):
    return Path('A1AF', f'QLAB_{case_id}', f'{file_type}{case_id}.txt')

  file_path = get_file_path(case_id, 'LA')
  db_LA = process_one_file(file_path)

  file_path = get_file_path(case_id, 'LV')
  db_LV = process_one_file(file_path)

  file_path = get_file_path(case_id, 'RV')
  db_RV = process_one_file(file_path)
  
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
  files = ['LA', 'LV', 'RV']


  curves_all_section_db = {}

  print
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

          file_section_key_name = f'Curves_{file_section_name}_{key}'
          #print(f'\tkey:{file_section_key_name}')
          #print(f'\t\tdata:{data}')
          section_db = curves_all_section_db.setdefault(file_section_key_name, {})
          section_db[case_id] = data
    pass


  for sec_name, data in curves_all_section_db.items():
    print(f'section: {sec_name}')
    for id, vals in data.items():
      #print(f'\tid:{id}, {vals}')
      print(f'\tid:{id}, {len(vals)}')

      pass
    print('*'*40)
    pass

  for sec_name, data in curves_all_section_db.items():
    print(f'section: {sec_name}')
    df = pd.DataFrame.from_dict(data)

    print(df.T)
    output_file_path = output_path.joinpath(f'{sec_name}.csv')
    df.T.to_csv(output_file_path)
    pass
  
  return

def data_process_general(output_path, case_list, cases_db_list):
  files = ['LA', 'LV', 'RV']  
  
  output_dict = {}
  for case_id, one_case_db in zip(case_list, cases_db_list):
    print(f'{case_id}')
    one_case_processed_done = data_process(one_case_db)
    output_dict[case_id] = one_case_processed_done
    #print(one_attrs)

  df = pd.DataFrame.from_dict(output_dict)
  print(df)
  output_file_path = output_path.joinpath(f'summary.csv')
  df.T.to_csv(output_file_path)
  return

def init(cur_path):
  output_path = Path(cur_path, 'output')
  #os.removedirs(output_path)
  shutil.rmtree(output_path, ignore_errors=True)
  if not os.path.exists(output_path):
    os.makedirs(output_path)
  
  case_list = []
  input_path = cur_path.joinpath('A1AF')
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
  cur_path = Path(__file__).parent.resolve()
  output_path = Path(cur_path, 'output')
  #output_path_curves = output_path.joinpath('Curves')
  case_list = init(cur_path)

  #case_list = ['0002','0005','0007']
  cases_db_list = []
  for one_case in case_list:
    one_case_db = process_one_case(one_case)
    cases_db_list.append(one_case_db)
    pass

###############################
# process General
  data_process_general(output_path, case_list, cases_db_list)

###############################
# process curves
#  data_process_curves(output_path_curves, case_list, cases_db_list)
  return

if __name__ == '__main__':
  main()
  print('HI Russell')
  sys.exit(0)
