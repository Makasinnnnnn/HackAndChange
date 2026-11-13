const paths = {
  route: 'M5 19v-7a4 4 0 0 1 4-4h9m-4-4 4 4-4 4',
  progress: 'M5 19v-4m7 4V9m7 10V5',
  catalog: 'M12 7c-2.6-2-5.5-2.5-9-1v12c3.5-1.5 6.4-1 9 1m0-12c2.6-2 5.5-2.5 9-1v12c-3.5-1.5-6.4-1-9 1m0-12v12',
  jury: 'M7 4h10v5a5 5 0 0 1-10 0V4Zm0 2H4v2a3 3 0 0 0 3 3m10-5h3v2a3 3 0 0 1-3 3m-5 3v5m-4 1h8',
};

export function NavigationIcon({tab}: {tab: keyof typeof paths}) {
  return <svg aria-hidden="true" width="21" height="21" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
    <path d={paths[tab]}/>
  </svg>;
}
