import AsyncStorage from '@react-native-async-storage/async-storage';
const KEY = '@deprecio/favorites';
export async function getFavorites(): Promise<string[]> { return JSON.parse(await AsyncStorage.getItem(KEY) || '[]'); }
export async function setFavorite(id: string, enabled: boolean): Promise<string[]> {
  const current = await getFavorites();
  const next = enabled ? [...new Set([...current, id])] : current.filter((item) => item !== id);
  await AsyncStorage.setItem(KEY, JSON.stringify(next));
  return next;
}