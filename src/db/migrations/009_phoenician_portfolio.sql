-- ===================================================================
-- Migration 009: Phoenician Capital Portfolio Holdings
-- ===================================================================

-- Insert portfolio companies
INSERT INTO companies (ticker, name, gics_sector, gics_sub_industry, country, market_cap_usd) VALUES
('3445.T', 'RS Technologies Co., Ltd.', 'Technology', 'Electronics Hardware & Equipment', 'Japan', 500000000),
('APR.WA', 'Auto Partner S.A.', 'Consumer Discretionary', 'Auto Parts & Equipment', 'Poland', 800000000),
('ASAL.L', 'ASA International Group plc', 'Industrials', 'Trading Companies & Distributors', 'UK', 300000000),
('AT.L', 'Ashtead Technology Holdings plc', 'Industrials', 'Trading Companies & Distributors', 'UK', 450000000),
('DNP.WA', 'Dino Polska S.A.', 'Consumer Staples', 'Food Retail', 'Poland', 1200000000),
('FOOD.TO', 'Goodfood Market Corp.', 'Technology', 'Internet Retail', 'Canada', 100000000),
('GLOBUSSPF', 'Globus Spirits Limited', 'Consumer Staples', 'Beverages - Alcoholic', 'India', 400000000),
('GSY.TO', 'goeasy Ltd.', 'Financials', 'Consumer Finance', 'Canada', 600000000),
('INTR', 'Inter & Co., Inc.', 'Financials', 'Banks - Regional', 'Brazil', 5000000000),
('JET2.L', 'Jet2 plc', 'Consumer Discretionary', 'Airlines', 'UK', 1200000000),
('KRI.AT', 'Kri-Kri Milk Industry S.A.', 'Consumer Staples', 'Dairy Products', 'Greece', 150000000),
('LOVE.V', 'Cannara Biotech Inc.', 'Consumer Discretionary', 'Cannabis', 'Canada', 150000000),
('MAD.AX', 'Mader Group Limited', 'Industrials', 'Building Products & Equipment', 'Australia', 200000000),
('PUUILO.HE', 'Puuilo Oyj', 'Consumer Discretionary', 'Specialty Retail', 'Finland', 350000000),
('QES.SI', 'China Sunsine Chemical Holdings Ltd.', 'Materials', 'Chemicals', 'Singapore', 900000000),
('SNT.WA', 'Synektik S.A.', 'Technology', 'Electronics Hardware & Equipment', 'Poland', 200000000),
('SPSY.L', 'Spectra Systems Corporation', 'Technology', 'Software & Services', 'UK', 75000000),
('TEQ.ST', 'Teqnion AB', 'Industrials', 'Machinery', 'Sweden', 300000000),
('TNOM.HE', 'Talenom Oyj', 'Financials', 'Accounting & Bookkeeping', 'Finland', 500000000);

-- Insert as active portfolio holdings
INSERT INTO portfolio_holdings (ticker, name, sector, is_active) VALUES
('3445.T', 'RS Technologies Co., Ltd.', 'Technology', TRUE),
('APR.WA', 'Auto Partner S.A.', 'Consumer Discretionary', TRUE),
('ASAL.L', 'ASA International Group plc', 'Industrials', TRUE),
('AT.L', 'Ashtead Technology Holdings plc', 'Industrials', TRUE),
('DNP.WA', 'Dino Polska S.A.', 'Consumer Staples', TRUE),
('FOOD.TO', 'Goodfood Market Corp.', 'Technology', TRUE),
('GLOBUSSPF', 'Globus Spirits Limited', 'Consumer Staples', TRUE),
('GSY.TO', 'goeasy Ltd.', 'Financials', TRUE),
('INTR', 'Inter & Co., Inc.', 'Financials', TRUE),
('JET2.L', 'Jet2 plc', 'Consumer Discretionary', TRUE),
('KRI.AT', 'Kri-Kri Milk Industry S.A.', 'Consumer Staples', TRUE),
('LOVE.V', 'Cannara Biotech Inc.', 'Consumer Discretionary', TRUE),
('MAD.AX', 'Mader Group Limited', 'Industrials', TRUE),
('PUUILO.HE', 'Puuilo Oyj', 'Consumer Discretionary', TRUE),
('QES.SI', 'China Sunsine Chemical Holdings Ltd.', 'Materials', TRUE),
('SNT.WA', 'Synektik S.A.', 'Technology', TRUE),
('SPSY.L', 'Spectra Systems Corporation', 'Technology', TRUE),
('TEQ.ST', 'Teqnion AB', 'Industrials', TRUE),
('TNOM.HE', 'Talenom Oyj', 'Financials', TRUE);
