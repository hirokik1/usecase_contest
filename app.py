from pydub import AudioSegment
from flask import Flask, render_template
from flask_cors import CORS
from ibm_watson import SpeechToTextV1
from ibm_watson import NaturalLanguageUnderstandingV1
from ibm_watson.natural_language_understanding_v1 import Features, KeywordsOptions
from ibm_watson import DiscoveryV2
from ibm_cloud_sdk_core.authenticators import IAMAuthenticator
from ibm_cloud_sdk_core import get_authenticator_from_environment
from flask_socketio import SocketIO, emit
from dotenv import load_dotenv
import datetime
import io
import os

# 環境変数の設定
load_dotenv()
stt_apikey = os.getenv('STT_APIKEY')
stt_url = os.getenv('STT_URL')
language_model_id = os.getenv('LANGUAGE_MODEL_ID')
nlu_apikey = os.getenv('NLU_APIKEY')
nlu_url = os.getenv('NLU_URL')
wd_apikey = os.getenv('WD_APIKEY')
wd_url = os.getenv('WD_URL')
wd_project_id = os.getenv('WD_PROJECT_ID')
cors_origins = os.environ.get('CORS_ORIGINS', '*').split(',')
print(cors_origins)

app = Flask(__name__)
socketio = SocketIO(app, async_mode='eventlet', logger=True, engineio_logger=True, cors_allowed_origins=cors_origins)
CORS(app, origins=cors_origins)

# IBM Watson Speech to Textサービスの設定
authenticator = IAMAuthenticator(stt_apikey)
stt = SpeechToTextV1(authenticator=authenticator)
stt.set_service_url(stt_url)

# IBM Watson Natural Language Understandingの設定
nlu_authenticator = IAMAuthenticator(nlu_apikey)
natural_language_understanding = NaturalLanguageUnderstandingV1(
    version='2023-05-28',  # ここで使用するAPIのバージョンを指定します
    authenticator=nlu_authenticator
)
natural_language_understanding.set_service_url(nlu_url)  

# IBM Watson Discoveryの設定
wd_authenticator = IAMAuthenticator(wd_apikey)
discovery = DiscoveryV2(
    version='2023-05-28',  # ここで使用するAPIのバージョンを指定します
    authenticator=wd_authenticator
)
discovery.set_service_url(wd_url)  
wd_project_id = wd_project_id

# スピーカーマッピング関数
def map_speaker_to_transcript(response):
    speaker_mapping = {}
    current_speaker = None
    current_transcript = []

    if 'speaker_labels' in response:
        for speaker_label in response['speaker_labels']:
            from_time = speaker_label['from']
            to_time = speaker_label['to']
            speaker = speaker_label['speaker']

            # スピーカーIDと時間をキーとする
            key = f"{speaker}_{from_time}_{to_time}"

            if current_speaker is None:
                current_speaker = speaker
            elif current_speaker != speaker:
                # スピーカーが変わった場合、前のスピーカーの発言をまとめる
                speaker_transcript = ''.join(current_transcript)
                speaker_mapping[f"{current_speaker}_{from_time}_{to_time}"] = speaker_transcript
                # speaker_mapping[f"{from_time}_{to_time}"] = speaker_transcript
                current_transcript = []
                current_speaker = speaker

            for result in response['results']:
                for alternative in result['alternatives']:
                    if alternative['confidence'] >= 0.5:  # 信頼度で絞り込む
                        for timestamp in alternative['timestamps']:
                            word, word_from_time, word_to_time = timestamp
                            if from_time <= word_from_time < to_time:
                                current_transcript.append(word)

        # 最後のスピーカーの発言をまとめる
        if current_speaker is not None and len(current_transcript) > 0:
            speaker_transcript = ''.join(current_transcript)
            speaker_mapping[f"{current_speaker}_{from_time}_{to_time}"] = speaker_transcript
            # speaker_mapping[f"{from_time}_{to_time}"] = speaker_transcript

        return speaker_mapping
    
    else:
        print('No speaker labels in the response.')
        return

@socketio.on('audio')
def handle_audio(audio_data):
    # ファイル名のタイムスタンプの生成
    timestamp = datetime.datetime.now().strftime("%Y_%m_%d-%H_%M_%S")

    # audio_dataをファイルに保存する
    # with open(f'audio/audio_{timestamp}.webm', 'wb') as file:
    #     file.write(audio_data)

    # 音声データをメモリに保存する
    audio_file_webm = io.BytesIO(audio_data)

    # 音声データが100バイト未満の場合は、Watson Speech to Textに送信しない
    if len(audio_data) < 100:
        print("data size was less than 100 bytes")
        return

    # 音声をテキストに変換する
    # audio_file_webm.seek(0)  # BytesIO objectのポインタを先頭に移動します
    result = stt.recognize(
        audio=audio_file_webm.read(),
        # audio=audio_name, # debug
        content_type='audio/webm;codecs=opus',
        model="ja-JP_BroadbandModel",
        language_customization_id=language_model_id,
        speaker_labels=True,
        ).get_result()
    
    # debug
    # print(result)

    # 音声が短すぎるといった理由でテキスト化できていない場合はそこで処理終了
    if 'speaker_labels' not in result:
        print('No speaker labels in the response. Skipping this audio segment.')
        return

    # スピーカーマッピング関数を呼び出して結果を取得する
    speaker_transcripts = map_speaker_to_transcript(result)

    # テキストをファイルに保存する
    transcript_name = f"transcripts/{timestamp}_transcript.txt"
    formatted_transcript = '' # Natural Language Understandingに送るテキスト
    formatted_transcript_with_speaker = ''   # transcriptファイルに保存するテキスト

    # with open(transcript_name, 'w') as f:
    for key, transcript in speaker_transcripts.items():
        # temp_formatted_transcript_with_speaker = f"Speaker {key}: {transcript}\n"
        temp_formatted_transcript = f"{transcript}\n"
        # f.write(temp_formatted_transcript_with_speaker)
        formatted_transcript += temp_formatted_transcript
        # formatted_transcript_with_speaker += temp_formatted_transcript_with_speaker
    

    # debug
    print("formatted_transcript: "+formatted_transcript)

    # テキストからキーワードを抽出する
    nlu_response = natural_language_understanding.analyze(
        text=formatted_transcript,
        features=Features(keywords=KeywordsOptions(limit=3))).get_result()
    
    # print("nlu_response:")
    # print(nlu_response)

    # キーワードをファイルに保存する
    '''
    keyword_file_name = f"keywords/{timestamp}_keyword.txt"
    with open(keyword_file_name, 'w') as f:
        for keyword in nlu_response['keywords']:
            f.write(keyword['text'] + '\n')
    '''

    # キーワードごとにドキュメントの検索を行う
    search_file_name = f"search/{timestamp}_search.txt"
    response_data = []
    # with open(search_file_name, 'w') as f:
    for keyword in nlu_response['keywords']:
        discovery_result = discovery.query(
            project_id=wd_project_id,
            natural_language_query=keyword['text'],
            count=3,
        ).get_result()

        found_results = False
        temp_results = []  # 一時的に結果を保存するためのリスト

        # キーワードと検索結果を書き込む
        # f.write(f"Keyword: {keyword['text']}\n")

        if 'results' in discovery_result:
            results = discovery_result['results']
            for i, result in enumerate(results):
                # if i > 0:
                #     f.write('---\n')  # 検索結果の切れ目を表示する

                if 'document_passages' in result:
                    document_passages = result['document_passages']
                    if document_passages:
                        for passage in document_passages:
                            passage_text = passage['passage_text']
                            # f.write(passage_text + '\n')
                            temp_results.append(passage_text)
                            found_results = True  # 検索結果が見つかったのでフラグを立てる

            # if not found_results:
                # f.write("検索結果なし\n")
                # response_entry["results"].append("検索結果なし")
        # else:
            # f.write("検索結果なし\n")
            # response_entry["results"].append("検索結果なし")

        # f.write('\n')
        if found_results:
            response_data.append({"keyword": keyword['text'], "results": temp_results})

    # ファイルに書き込んだ内容をクライアントに送信する
    emit('response', response_data)
    print(response_data)
    
@app.route('/')
def index():
    return render_template('index.html')

if __name__ == '__main__':
    socketio.run(app, port=8080, debug=True)

