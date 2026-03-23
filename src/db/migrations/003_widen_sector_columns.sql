-- Migration 003: widen sector/industry columns to hold full FMP text values
ALTER TABLE companies
    ALTER COLUMN gics_sector          TYPE VARCHAR(100),
    ALTER COLUMN gics_industry_group  TYPE VARCHAR(100),
    ALTER COLUMN gics_industry        TYPE VARCHAR(100),
    ALTER COLUMN gics_sub_industry    TYPE VARCHAR(100);
