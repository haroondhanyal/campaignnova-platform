import countryData from './country-data.json';

function flag(countryCode:string){
  return String.fromCodePoint(...[...countryCode].map(letter=>127397+letter.charCodeAt(0)));
}

export const countries=countryData.map(([name,code,callingCode])=>[
  name,callingCode,flag(code),code,
] as const);
