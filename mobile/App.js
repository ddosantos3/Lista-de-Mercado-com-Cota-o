import React, { useEffect, useMemo, useState } from 'react';
import { ActivityIndicator, FlatList, Keyboard, Platform, SafeAreaView, ScrollView, StyleSheet, Text, TextInput, TouchableOpacity, View } from 'react-native';
import { StatusBar } from 'expo-status-bar';

const defaultHost = Platform.OS === 'android' ? '10.0.2.2' : '127.0.0.1';
const API_BASE = (process.env.EXPO_PUBLIC_API_BASE || `http://${defaultHost}:8000`).replace(/\/$/, '');

export default function App() {
  const [itemText, setItemText] = useState('');
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState(null);
  const [history, setHistory] = useState([]);
  const [historyLoading, setHistoryLoading] = useState(false);

  const API_URL = `${API_BASE}/cotar/`;

  const suggestions = ['arroz','feijão','óleo','café','açúcar','trigo','leite'];

  const canQuote = items.length > 0 && !loading;

  function addItem() {
    const v = itemText.trim();
    if (!v) return;
    setItems(prev => [...prev, v]);
    setItemText('');
    Keyboard.dismiss();
  }

  function removeItem(idx) {
    setItems(prev => prev.filter((_, i) => i !== idx));
  }

  async function loadHistory() {
    setHistoryLoading(true);
    try {
      const r = await fetch(`${API_BASE}/cotacoes_summary?limit=20`);
      if (!r.ok) throw new Error('hist');
      const js = await r.json();
      setHistory(js.items || []);
    } catch (e) {
      setHistory([]);
    } finally {
      setHistoryLoading(false);
    }
  }

  async function fetchQuote() {
    setLoading(true);
    setResults(null);
    try {
      const r = await fetch(API_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ itens: items })
      });
      if (!r.ok) throw new Error('api');
      const js = await r.json();
      setResults(js);
      loadHistory();
    } catch (e) {
      setResults({ error: 'Falha ao conectar com o backend.' });
    } finally {
      setLoading(false);
    }
  }

  async function openHistoryItem(id) {
    try {
      const r = await fetch(`${API_BASE}/cotacoes/${id}`);
      if (!r.ok) return;
      const js = await r.json();
      setResults(js);
    } catch (e) {}
  }

  useEffect(() => { loadHistory(); }, []);

  const totalsSorted = useMemo(() => {
    if (!results || !results.totais_por_mercado) return [];
    return Object.entries(results.totais_por_mercado).sort((a,b) => a[1] - b[1]);
  }, [results]);

  const best = useMemo(() => {
    if (!totalsSorted.length) return null;
    return { market: totalsSorted[0][0], total: totalsSorted[0][1] };
  }, [totalsSorted]);

  return (
    <SafeAreaView style={styles.safe}>
      <StatusBar style="dark" />
      <ScrollView contentContainerStyle={styles.container} keyboardShouldPersistTaps="handled">
        <Text style={styles.title}>🛒 Cotador de Compras</Text>
        <Text style={styles.subtitle}>API: {API_BASE}</Text>

        <View style={styles.card}>
          <Text style={styles.cardTitle}>Adicionar Itens</Text>
          <View style={styles.row}>
            <TextInput
              placeholder="Ex: arroz, feijão, café..."
              value={itemText}
              onChangeText={setItemText}
              style={styles.input}
              onSubmitEditing={addItem}
              returnKeyType="done"
            />
            <TouchableOpacity style={[styles.btn, styles.btnPrimary]} onPress={addItem}>
              <Text style={styles.btnText}>Adicionar</Text>
            </TouchableOpacity>
          </View>
          <View style={styles.suggestions}>
            {suggestions.map(s => (
              <TouchableOpacity key={s} style={styles.chip} onPress={() => setItemText(s)}>
                <Text>{s}</Text>
              </TouchableOpacity>
            ))}
          </View>
        </View>

        <View style={styles.card}>
          <Text style={styles.cardTitle}>Sua Lista</Text>
          {items.length === 0 ? (
            <Text style={styles.placeholder}>Sua lista está vazia.</Text>
          ) : (
            items.map((t, idx) => (
              <View key={`${t}-${idx}`} style={styles.listRow}>
                <Text style={{flex:1}} numberOfLines={1}>{t}</Text>
                <TouchableOpacity onPress={() => removeItem(idx)}>
                  <Text style={{color:'#b91c1c'}}>remover</Text>
                </TouchableOpacity>
              </View>
            ))
          )}
          <TouchableOpacity
            disabled={!canQuote}
            onPress={fetchQuote}
            style={[styles.btn, canQuote ? styles.btnSuccess : styles.btnDisabled]}
          >
            {loading ? <ActivityIndicator color="#fff"/> : <Text style={styles.btnText}>Cotar Preços Agora</Text>}
          </TouchableOpacity>
        </View>

        <View style={styles.grid}>
          <View style={[styles.card, {flex:2}]}> 
            <Text style={styles.cardTitle}>Resultado</Text>
            {!results && <Text style={styles.placeholder}>Nenhuma cotação ainda.</Text>}
            {results && results.error && <Text style={{color:'#b91c1c'}}>{results.error}</Text>}
            {results && !results.error && (
              <View>
                <Text style={styles.info}>Cotação de: <Text style={styles.infoStrong}>{results.requested_at || '-'}</Text></Text>
                <Text style={styles.infoSmall}>Fonte: {results.source || 'n/d'} | Moeda: {results.currency || 'BRL'}</Text>
                {best && (
                  <View style={styles.highlight}>
                    <Text style={styles.highlightTitle}>Melhor opção encontrada!</Text>
                    <Text>Mercado: <Text style={styles.infoStrong}>{best.market.replace('_',' ')}</Text> | Total: <Text style={styles.infoStrong}>R$ {best.total.toFixed(2)}</Text></Text>
                  </View>
                )}
                <Text style={[styles.cardTitle, {marginTop:10}]}>Detalhes</Text>
                {totalsSorted.map(([market, total]) => (
                  <View key={market} style={styles.marketCard}>
                    <View style={styles.marketHeader}>
                      <Text style={styles.marketTitle}>{market.replace('_',' ')}</Text>
                      <Text style={styles.marketTotal}>R$ {total.toFixed(2)}</Text>
                    </View>
                    {((results.cotacoes_detalhadas || {})[market] || []).map((it, i) => (
                      <View key={i} style={styles.itemRow}>
                        <View style={{flex:1}}>
                          <Text style={styles.itemName}>{it.item_encontrado}</Text>
                          <Text style={styles.itemSublabel}>(Buscado por: "{it.item_buscado}")</Text>
                        </View>
                        <Text style={styles.itemPrice}>{it.preco > 0 ? `R$ ${it.preco.toFixed(2)}` : 'Não encontrado'}</Text>
                      </View>
                    ))}
                  </View>
                ))}
              </View>
            )}
          </View>

          <View style={[styles.card, {flex:1}]}> 
            <View style={styles.rowBetween}>
              <Text style={styles.cardTitle}>Histórico</Text>
              <TouchableOpacity onPress={loadHistory} style={[styles.btn, styles.btnLight, {paddingVertical:6}] }>
                {historyLoading ? <ActivityIndicator /> : <Text>Atualizar</Text>}
              </TouchableOpacity>
            </View>
            {history.length === 0 ? (
              <Text style={styles.placeholder}>Sem cotações ainda.</Text>
            ) : (
              <FlatList
                data={history}
                keyExtractor={(i) => i.id}
                renderItem={({item}) => (
                  <TouchableOpacity onPress={() => openHistoryItem(item.id)} style={styles.historyRow}>
                    <View>
                      <Text style={styles.historyDate}>{item.requested_at || '-'}</Text>
                      <Text style={styles.historySubtitle}>{item.best_market ? item.best_market.replace('_',' ') : '-'}</Text>
                    </View>
                    <Text style={styles.historyTotal}>{item.best_total != null ? `R$ ${item.best_total.toFixed(2)}` : '-'}</Text>
                  </TouchableOpacity>
                )}
              />
            )}
          </View>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: '#f9fafb' },
  container: { padding: 16 },
  title: { fontSize: 24, fontWeight: '700', marginBottom: 4 },
  subtitle: { color:'#6b7280', marginBottom: 12 },
  card: { backgroundColor:'#fff', padding: 16, borderRadius: 12, marginBottom: 12, shadowColor:'#000', shadowOpacity:0.05, shadowRadius:6, elevation:1 },
  cardTitle: { fontSize: 16, fontWeight: '600', marginBottom: 8 },
  row: { flexDirection:'row', gap: 8 },
  rowBetween: { flexDirection:'row', justifyContent:'space-between', alignItems:'center' },
  input: { flex:1, borderColor:'#e5e7eb', borderWidth:1, borderRadius:8, paddingHorizontal:12, paddingVertical:12 },
  btn: { borderRadius:8, paddingHorizontal:14, paddingVertical:12, alignItems:'center', justifyContent:'center' },
  btnPrimary: { backgroundColor:'#4f46e5' },
  btnSuccess: { backgroundColor:'#16a34a', marginTop: 12 },
  btnDisabled: { backgroundColor:'#9ca3af', marginTop: 12 },
  btnLight: { backgroundColor:'#f3f4f6' },
  btnText: { color:'#fff', fontWeight:'600' },
  suggestions: { flexDirection:'row', flexWrap:'wrap', gap:8 },
  chip: { backgroundColor:'#f3f4f6', paddingHorizontal:8, paddingVertical:6, borderRadius:8 },
  placeholder: { color:'#6b7280', fontStyle:'italic' },
  listRow: { flexDirection:'row', alignItems:'center', paddingVertical:8, borderBottomWidth:1, borderBottomColor:'#f3f4f6' },
  grid: { flexDirection:'row', gap:12 },
  highlight: { backgroundColor:'#ecfdf5', borderColor:'#34d399', borderWidth:1, padding:12, borderRadius:8, marginTop:8 },
  highlightTitle: { fontWeight:'700', marginBottom:4, color:'#065f46' },
  info: { color:'#374151' },
  infoStrong: { fontWeight:'700' },
  infoSmall: { color:'#6b7280', fontSize:12, marginBottom:8 },
  marketCard: { borderWidth:1, borderColor:'#e5e7eb', padding:10, borderRadius:8, marginBottom:8 },
  marketHeader: { flexDirection:'row', justifyContent:'space-between', alignItems:'center', marginBottom:6 },
  marketTitle: { fontSize:16, fontWeight:'600', textTransform:'capitalize' },
  marketTotal: { fontSize:18, fontWeight:'700' },
  itemRow: { flexDirection:'row', justifyContent:'space-between', alignItems:'center', paddingVertical:6, borderBottomWidth:1, borderBottomColor:'#f3f4f6' },
  itemName: { color:'#111827' },
  itemSublabel: { color:'#6b7280', fontSize:12 },
  itemPrice: { fontWeight:'600' },
  historyRow: { flexDirection:'row', justifyContent:'space-between', alignItems:'center', paddingVertical:10, borderBottomWidth:1, borderBottomColor:'#f3f4f6' },
  historyDate: { color:'#111827' },
  historySubtitle: { color:'#6b7280', fontSize:12 },
  historyTotal: { fontWeight:'700' }
});

