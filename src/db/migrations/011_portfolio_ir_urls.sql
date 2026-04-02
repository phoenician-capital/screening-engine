-- ===================================================================
-- Migration 011: Add IR/events URLs to portfolio_holdings
-- ===================================================================

ALTER TABLE portfolio_holdings
    ADD COLUMN IF NOT EXISTS ir_url     TEXT,
    ADD COLUMN IF NOT EXISTS events_url TEXT;

-- Update all holdings with their IR and events URLs
UPDATE portfolio_holdings SET
    ir_url     = 'https://www.rs-tec.jp/en/ir/',
    events_url = 'https://www.rs-tec.jp/en/ir/library/calendar/'
WHERE ticker = '3445.T';

UPDATE portfolio_holdings SET
    ir_url     = 'https://www.autopartner.com/en/investor-relations/',
    events_url = 'https://www.autopartner.com/en/investor-relations/events/'
WHERE ticker = 'APR.WA';

UPDATE portfolio_holdings SET
    ir_url     = 'https://www.asainternational.com/investor-relations/',
    events_url = 'https://www.asainternational.com/investor-relations/financial-calendar/'
WHERE ticker = 'ASAL.L';

UPDATE portfolio_holdings SET
    ir_url     = 'https://www.ashtead-technology.com/investor-relations/',
    events_url = 'https://www.ashtead-technology.com/investor-relations/financial-calendar/'
WHERE ticker = 'AT.L';

UPDATE portfolio_holdings SET
    ir_url     = 'https://grupadino.pl/en/wse/',
    events_url = 'https://grupadino.pl/en/calendar/'
WHERE ticker = 'DNP.WA';

UPDATE portfolio_holdings SET
    ir_url     = 'https://ir.goodfood.ca/',
    events_url = 'https://ir.goodfood.ca/events'
WHERE ticker = 'FOOD.TO';

UPDATE portfolio_holdings SET
    ir_url     = 'https://www.globusspirits.com/investors.php',
    events_url = 'https://www.globusspirits.com/investors.php'
WHERE ticker = 'GLOBUSSPF';

UPDATE portfolio_holdings SET
    ir_url     = 'https://investors.goeasy.com/investor-overview',
    events_url = 'https://investors.goeasy.com/events-and-presentations/upcoming-events'
WHERE ticker = 'GSY.TO';

UPDATE portfolio_holdings SET
    ir_url     = 'https://investors.inter.co/en/',
    events_url = 'https://investors.inter.co/en/investor-updates/agenda/'
WHERE ticker = 'INTR';

UPDATE portfolio_holdings SET
    ir_url     = 'https://www.jet2plc.com/en/investor_relations',
    events_url = 'https://www.jet2plc.com/en/financial-calendar'
WHERE ticker = 'JET2.L';

UPDATE portfolio_holdings SET
    ir_url     = 'https://www.krikri.gr/investorsen/',
    events_url = 'https://www.krikri.gr/toolsen/120/'
WHERE ticker = 'KRI.AT';

UPDATE portfolio_holdings SET
    ir_url     = 'https://www.cannara.ca/investors/',
    events_url = 'https://www.cannara.ca/en/investor-area/company-events/'
WHERE ticker = 'LOVE.V';

UPDATE portfolio_holdings SET
    ir_url     = 'https://www.madergroup.com.au/investors/',
    events_url = 'https://www.madergroup.com.au/investors/announcements-and-presentations/'
WHERE ticker = 'MAD.AX';

UPDATE portfolio_holdings SET
    ir_url     = 'https://investors.puuilo.fi/',
    events_url = 'https://investors.puuilo.fi/en/financial-calendar'
WHERE ticker = 'PUUILO.HE';

UPDATE portfolio_holdings SET
    ir_url     = 'https://chinasunsine.com/investors/',
    events_url = 'https://chinasunsine.com/investors/investor-events/'
WHERE ticker = 'QES.SI';

UPDATE portfolio_holdings SET
    ir_url     = 'https://synektik.com.pl/en/investor-centre/',
    events_url = 'https://synektik.com.pl/en/investor-centre/calendar/'
WHERE ticker = 'SNT.WA';

UPDATE portfolio_holdings SET
    ir_url     = 'https://www.spsy.com/investor-relations/',
    events_url = 'https://www.spsy.com/investor-relations/regulatory-news/'
WHERE ticker = 'SPSY.L';

UPDATE portfolio_holdings SET
    ir_url     = 'https://www.teqnion.se/en/investor-relations/',
    events_url = 'https://www.teqnion.se/en/investor-relations/financial-calendar/'
WHERE ticker = 'TEQ.ST';

UPDATE portfolio_holdings SET
    ir_url     = 'https://www.talenom.fi/en/investor-relations/',
    events_url = 'https://www.talenom.fi/en/investor-relations/financial-calendar/'
WHERE ticker = 'TNOM.HE';
