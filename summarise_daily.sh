#!/bin/bash

cd csvs
for f in */*.csv; do
  echo $f `csvtool height "$f"`
done